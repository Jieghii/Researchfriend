"""业务辅助：重合度、在线、推荐排除、可见性过滤。"""
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import aliased

from extensions import db
from models import (
    Comment,
    Conversation,
    FriendRequest,
    Friendship,
    Like,
    Message,
    Skip,
    Tag,
    Thought,
    ThoughtTag,
    User,
    UserTag,
)

ONLINE_MINUTES = 5
REJECT_COOLDOWN_DAYS = 7

PRESET_INDUSTRIES = [
    "白酒", "啤酒", "调味品", "乳制品", "半导体", "消费电子",
    "新能源车", "光伏", "储能", "医药", "CXO", "军工",
    "银行", "地产", "互联网", "港股互联网",
]
PRESET_STOCKS = [
    "贵州茅台", "五粮液", "宁德时代", "比亚迪", "隆基绿能",
    "中芯国际", "腾讯控股", "美团", "药明康德", "海天味业",
]
YEAR_OPTIONS = ["<1年", "1-3年", "3-5年", "5-10年", "10-15年", "15年+"]
MAX_TAGS = 10
TAG_LIMIT_MSG = "最多选 10 个，先取消一个再加吧"


def now_utc():
    return datetime.utcnow()


def is_online(user):
    if not user or not user.last_active_at:
        return False
    return now_utc() - user.last_active_at <= timedelta(minutes=ONLINE_MINUTES)


def relative_active(user):
    if is_online(user):
        return "在线"
    if not user.last_active_at:
        return "很久未活跃"
    delta = now_utc() - user.last_active_at
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{seconds // 60}分钟前"
    if seconds < 3600 * 24:
        hours = seconds // 3600
        if hours < 3:
            return f"{hours}小时前活跃" if False else f"{hours}小时前"
        return f"{hours}小时前"
    yesterday = now_utc().date() - timedelta(days=1)
    if user.last_active_at.date() == yesterday:
        return "昨天"
    return f"{user.last_active_at.month}月{user.last_active_at.day}日"


def avatar_index(nickname: str) -> int:
    h = 0
    for ch in nickname or "":
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % 8


def overlap_pct(my_tag_ids, other_tag_ids):
    a = set(my_tag_ids or [])
    b = set(other_tag_ids or [])
    union = a | b
    if not union:
        return None
    inter = a & b
    raw = round(len(inter) / len(union) * 100, 2)
    return int(round(raw))


def tag_ids_of(user_id):
    rows = UserTag.query.filter_by(user_id=user_id).all()
    return [r.tag_id for r in rows]


def tags_map_for_users(user_ids):
    if not user_ids:
        return {}
    rows = (
        db.session.query(UserTag.user_id, Tag)
        .join(Tag, Tag.id == UserTag.tag_id)
        .filter(UserTag.user_id.in_(user_ids))
        .all()
    )
    out = {uid: [] for uid in user_ids}
    for uid, tag in rows:
        out.setdefault(uid, []).append(tag)
    return out


def pair_ids(a, b):
    return (a, b) if a < b else (b, a)


def are_friends(a, b):
    low, high = pair_ids(a, b)
    return Friendship.query.filter_by(user_low_id=low, user_high_id=high).first() is not None


def friend_ids(user_id):
    rows = Friendship.query.filter(
        or_(Friendship.user_low_id == user_id, Friendship.user_high_id == user_id)
    ).all()
    ids = []
    for r in rows:
        ids.append(r.user_high_id if r.user_low_id == user_id else r.user_low_id)
    return ids


def mark_conversation_read(conv_id, me_id):
    Message.query.filter(
        Message.conversation_id == conv_id,
        Message.sender_id != me_id,
        Message.is_read.is_(False),
    ).update({"is_read": True}, synchronize_session=False)
    db.session.commit()


def conversation_inbox(me):
    convs = (
        Conversation.query.filter(or_(Conversation.user_a_id == me.id, Conversation.user_b_id == me.id))
        .order_by(Conversation.last_message_at.desc())
        .all()
    )
    if not convs:
        return []
    conv_ids = [c.id for c in convs]
    peer_ids = [c.user_b_id if c.user_a_id == me.id else c.user_a_id for c in convs]
    peers = {u.id: u for u in User.query.filter(User.id.in_(peer_ids)).all()}
    latest_rows = (
        db.session.query(Message.conversation_id, func.max(Message.id))
        .filter(Message.conversation_id.in_(conv_ids))
        .group_by(Message.conversation_id)
        .all()
    )
    latest_ids = [mid for _, mid in latest_rows if mid]
    last_by_conv = {}
    if latest_ids:
        for m in Message.query.filter(Message.id.in_(latest_ids)).all():
            last_by_conv[m.conversation_id] = m
    unread_rows = (
        db.session.query(Message.conversation_id, func.count(Message.id))
        .filter(
            Message.conversation_id.in_(conv_ids),
            Message.sender_id != me.id,
            Message.is_read.is_(False),
        )
        .group_by(Message.conversation_id)
        .all()
    )
    unread_map = {cid: n for cid, n in unread_rows}
    items = []
    for conv in convs:
        peer = peers.get(conv.user_b_id if conv.user_a_id == me.id else conv.user_a_id)
        if not peer:
            continue
        last = last_by_conv.get(conv.id)
        if not last:
            continue
        preview = last.content
        if last.sender_id == me.id:
            preview = "我：" + preview
        items.append(
            {
                "conv": conv,
                "peer": user_brief(peer, me),
                "preview": preview,
                "time": relative_time(last.created_at if last else conv.last_message_at),
                "unread": unread_map.get(conv.id, 0),
            }
        )
    return items


def get_or_create_conversation(me_id, peer_id, source_tag_id=None):
    low, high = pair_ids(me_id, peer_id)
    conv = Conversation.query.filter_by(user_a_id=low, user_b_id=high).first()
    if conv:
        if source_tag_id and not conv.source_tag_id:
            conv.source_tag_id = source_tag_id
            db.session.commit()
        return conv
    conv = Conversation(user_a_id=low, user_b_id=high, source_tag_id=source_tag_id)
    db.session.add(conv)
    db.session.commit()
    return conv


def pending_from_me(me_id):
    rows = FriendRequest.query.filter_by(from_user_id=me_id, status="pending").all()
    return {r.to_user_id for r in rows}


def pending_to_me(me_id):
    rows = FriendRequest.query.filter_by(to_user_id=me_id, status="pending").all()
    return {r.from_user_id for r in rows}


def excluded_user_ids(me_id):
    """A 文档 4.2：七类不得出现在推荐/匹配中。"""
    excluded = {me_id}
    excluded.update(friend_ids(me_id))
    excluded.update(pending_from_me(me_id))
    for s in Skip.query.filter_by(user_id=me_id).all():
        excluded.add(s.skipped_user_id)
    for s in Skip.query.filter_by(skipped_user_id=me_id).all():
        excluded.add(s.user_id)
    since = now_utc() - timedelta(days=REJECT_COOLDOWN_DAYS)
    rejected = FriendRequest.query.filter(
        FriendRequest.status == "rejected",
        FriendRequest.responded_at >= since,
        or_(
            FriendRequest.from_user_id == me_id,
            FriendRequest.to_user_id == me_id,
        ),
    ).all()
    for r in rejected:
        other = r.to_user_id if r.from_user_id == me_id else r.from_user_id
        excluded.add(other)
    return excluded


def recommend_candidates(me, limit=20, offset=0, extra_exclude=None):
    excluded = excluded_user_ids(me.id)
    if extra_exclude:
        excluded.update(extra_exclude)
    my_tags = set(tag_ids_of(me.id))
    q = User.query.filter(User.id.notin_(excluded) if excluded else True)
    q = q.filter(User.role.isnot(None), User.years.isnot(None))
    users = q.all()
    tmap = tags_map_for_users([u.id for u in users])

    scored = []
    zero_overlap = 0
    for u in users:
        tids = [t.id for t in tmap.get(u.id, [])]
        common = my_tags & set(tids)
        pct = overlap_pct(my_tags, tids)
        if not common:
            zero_overlap += 1
        scored.append(
            {
                "user": u,
                "tags": tmap.get(u.id, []),
                "common_ids": common,
                "pct": pct,
                "online": is_online(u),
                "has_common": len(common) > 0,
            }
        )
    scored.sort(
        key=lambda x: (
            not x["has_common"],
            not x["online"],
            -(x["pct"] if x["pct"] is not None else -1),
            -(x["user"].last_active_at.timestamp() if x["user"].last_active_at else 0),
        )
    )
    batch = scored[offset : offset + limit]
    return batch, len(scored), zero_overlap


def card_payload(me, item):
    u = item["user"]
    my_ids = set(tag_ids_of(me.id))
    common = [t for t in item["tags"] if t.id in my_ids]
    other = [t for t in item["tags"] if t.id not in my_ids]
    extra_common = max(0, len(common) - 5)
    extra_other = max(0, len(other) - 5)
    return {
        "id": u.id,
        "nickname": u.nickname,
        "role": "买方" if u.role == "buyer" else "卖方",
        "years": u.years,
        "online": item["online"],
        "active_text": relative_active(u),
        "pct": item["pct"],
        "avatar": avatar_index(u.nickname),
        "common": [{"id": t.id, "name": t.name} for t in common[:5]],
        "common_extra": extra_common,
        "other": [{"id": t.id, "name": t.name} for t in other[:5]],
        "other_extra": extra_other,
        "has_common": item["has_common"],
    }


def thought_visible_query(viewer):
    """服务端可见性过滤，不得把仅自己可见的内容交给前端隐藏。"""
    fid = friend_ids(viewer.id)
    conds = [Thought.visibility == "public"]
    conds.append(Thought.author_id == viewer.id)
    if fid:
        conds.append(and_(Thought.visibility == "friends", Thought.author_id.in_(fid)))
    return Thought.query.filter(or_(*conds))


def thought_visible_to(thought, viewer):
    if thought.author_id == viewer.id:
        return True
    if thought.visibility == "public":
        return True
    if thought.visibility == "friends" and are_friends(thought.author_id, viewer.id):
        return True
    return False


def serialize_thought(thought, viewer, tags_by_thought, likes_count, liked_ids, author, comments_count=0):
    tags = tags_by_thought.get(thought.id, [])
    return {
        "id": thought.id,
        "body": thought.body,
        "visibility": thought.visibility,
        "created_at": thought.created_at.isoformat() + "Z",
        "rel_time": relative_time(thought.created_at),
        "author": user_brief(author, viewer),
        "tags": [{"id": t.id, "name": t.name} for t in tags],
        "likes": likes_count.get(thought.id, 0),
        "liked": thought.id in liked_ids,
        "comments": comments_count,
        "mine": thought.author_id == viewer.id,
        "locked": thought.visibility == "self",
    }


def user_brief(u, viewer=None):
    pct = None
    common = []
    if viewer and u.id != viewer.id:
        mine = tag_ids_of(viewer.id)
        theirs = tag_ids_of(u.id)
        pct = overlap_pct(mine, theirs)
        common_ids = set(mine) & set(theirs)
        if common_ids:
            common = Tag.query.filter(Tag.id.in_(common_ids)).all()
    return {
        "id": u.id,
        "nickname": u.nickname,
        "role": "买方" if u.role == "buyer" else ("卖方" if u.role == "seller" else ""),
        "years": u.years or "",
        "online": is_online(u),
        "active_text": relative_active(u),
        "avatar": avatar_index(u.nickname),
        "pct": pct,
        "common": [{"id": t.id, "name": t.name} for t in common[:5]],
        "signature": u.signature or "",
    }


def relative_time(dt):
    if not dt:
        return ""
    delta = now_utc() - dt
    s = int(delta.total_seconds())
    if s < 60:
        return "刚刚"
    if s < 3600:
        return f"{s // 60}分钟前"
    if s < 86400:
        return f"{s // 3600}小时前"
    if s < 86400 * 2:
        return "昨天"
    return f"{dt.month}月{dt.day}日"


def format_msg_time(dt):
    today = now_utc().date()
    if dt.date() == today:
        return f"今天 {dt.strftime('%H:%M')}"
    if dt.date() == today - timedelta(days=1):
        return f"昨天 {dt.strftime('%H:%M')}"
    return f"{dt.month}月{dt.day}日 {dt.strftime('%H:%M')}"


def topic_heat(tag_id):
    start = datetime(now_utc().year, now_utc().month, now_utc().day)
    followers = UserTag.query.filter_by(tag_id=tag_id).count()
    conv_ids = [c.id for c in Conversation.query.filter_by(source_tag_id=tag_id).all()]
    talks = 0
    if conv_ids:
        talks = Message.query.filter(Message.conversation_id.in_(conv_ids), Message.created_at >= start).count()
    thought_ids = [r.thought_id for r in ThoughtTag.query.filter_by(tag_id=tag_id).all()]
    thoughts_today = 0
    if thought_ids:
        thoughts_today = Thought.query.filter(Thought.id.in_(thought_ids), Thought.created_at >= start).count()
    return talks * 2 + followers + thoughts_today * 3, followers, talks, thoughts_today


def recompute_hot_ranks():
    tags = Tag.query.all()
    scored = []
    for t in tags:
        heat, followers, talks, th = topic_heat(t.id)
        scored.append((heat, t, followers))
    scored.sort(key=lambda x: -x[0])
    for i, (heat, t, followers) in enumerate(scored, start=1):
        t.last_rank = t.current_rank
        t.current_rank = i if heat > 0 else None
    db.session.commit()
    top = []
    for heat, t, followers in scored[:5]:
        if heat <= 0:
            continue
        arrow = "flat"
        if t.last_rank and t.current_rank:
            if t.current_rank < t.last_rank:
                arrow = "up"
            elif t.current_rank > t.last_rank:
                arrow = "down"
        elif t.current_rank:
            arrow = "up"
        top.append({"tag": t, "heat": heat, "followers": followers, "arrow": arrow, "rank": t.current_rank})
    return top


def ensure_tag(name, kind="industry", preset=False):
    tag = Tag.query.filter_by(name=name).first()
    if tag:
        return tag
    tag = Tag(name=name, kind=kind, is_preset=preset)
    db.session.add(tag)
    db.session.flush()
    return tag


def likes_and_comments_for(thought_ids, viewer_id):
    likes_count = {tid: 0 for tid in thought_ids}
    comments_count = {tid: 0 for tid in thought_ids}
    liked_ids = set()
    if not thought_ids:
        return likes_count, liked_ids, comments_count
    for tid, n in (
        db.session.query(Like.thought_id, db.func.count(Like.id))
        .filter(Like.thought_id.in_(thought_ids))
        .group_by(Like.thought_id)
        .all()
    ):
        likes_count[tid] = n
    for tid, n in (
        db.session.query(Comment.thought_id, db.func.count(Comment.id))
        .filter(Comment.thought_id.in_(thought_ids))
        .group_by(Comment.thought_id)
        .all()
    ):
        comments_count[tid] = n
    liked_ids = {
        r.thought_id
        for r in Like.query.filter(Like.user_id == viewer_id, Like.thought_id.in_(thought_ids)).all()
    }
    return likes_count, liked_ids, comments_count


def tags_for_thoughts(thought_ids):
    out = {tid: [] for tid in thought_ids}
    if not thought_ids:
        return out
    rows = (
        db.session.query(ThoughtTag.thought_id, Tag)
        .join(Tag, Tag.id == ThoughtTag.tag_id)
        .filter(ThoughtTag.thought_id.in_(thought_ids))
        .all()
    )
    for tid, tag in rows:
        out.setdefault(tid, []).append(tag)
    return out
