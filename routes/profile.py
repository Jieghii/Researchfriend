from datetime import timedelta

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from extensions import db
from models import (
    Comment,
    Conversation,
    FriendRequest,
    Friendship,
    Like,
    Message,
    Tag,
    Thought,
    User,
    UserTag,
)
from routes.auth import current_user
from services import (
    PRESET_INDUSTRIES,
    PRESET_STOCKS,
    YEAR_OPTIONS,
    MAX_TAGS,
    TAG_LIMIT_MSG,
    EXP_RULES,
    REALMS,
    are_friends,
    avatar_index,
    daily_thought_limit,
    ensure_tag,
    friend_ids,
    is_online,
    now_utc,
    overlap_pct,
    pair_ids,
    realm_index,
    realm_of,
    realm_progress,
    relative_active,
    relative_time,
    serialize_thought,
    tag_ids_of,
    tags_for_thoughts,
    tags_map_for_users,
    thought_visible_query,
    today_exp_logs,
    user_brief,
    likes_and_comments_for,
)

bp = Blueprint("profile", __name__)


def accept_request_logic(me, req):
    req.status = "accepted"
    req.responded_at = now_utc()
    other = req.from_user_id if req.to_user_id == me.id else req.to_user_id
    low, high = pair_ids(me.id, other)
    if not Friendship.query.filter_by(user_low_id=low, user_high_id=high).first():
        db.session.add(Friendship(user_low_id=low, user_high_id=high, created_at=now_utc()))
    db.session.commit()
    return other


@bp.route("/me")
def me_page():
    me = current_user()
    liked = FriendRequest.query.filter_by(to_user_id=me.id).count()
    convs = Conversation.query.filter(
        (Conversation.user_a_id == me.id) | (Conversation.user_b_id == me.id)
    ).all()
    talked = 0
    for c in convs:
        if Message.query.filter_by(conversation_id=c.id).first():
            talked += 1
    thoughts_n = Thought.query.filter_by(author_id=me.id).count()
    pending_n = FriendRequest.query.filter_by(to_user_id=me.id, status="pending").count()
    my_tags = Tag.query.join(UserTag, UserTag.tag_id == Tag.id).filter(UserTag.user_id == me.id).all()
    fids = friend_ids(me.id)
    friends = User.query.filter(User.id.in_(fids)).all() if fids else []
    friends.sort(key=lambda u: (not is_online(u), -(u.last_active_at.timestamp() if u.last_active_at else 0)))
    items = Thought.query.filter_by(author_id=me.id).order_by(Thought.created_at.desc()).limit(10).all()
    bundled = []
    if items:
        tmap = tags_for_thoughts([t.id for t in items])
        likes_count, liked_ids, comments_count = likes_and_comments_for([t.id for t in items], me.id)
        bundled = [
            serialize_thought(t, me, tmap, likes_count, liked_ids, me, comments_count.get(t.id, 0)) for t in items
        ]
    from models import AdminNotice, InviteCode

    my_code = InviteCode.query.filter_by(owner_user_id=me.id).first()

    invite_left = max(0, my_code.max_uses - my_code.used_count) if my_code else 0

    return render_template(
        "me.html",
        nav="me",
        liked=liked,
        talked=talked,
        thoughts_n=thoughts_n,
        pending_n=pending_n,
        invite_left=invite_left,
        my_tags=my_tags,
        friends=friends[:8],
        friends_n=len(friends),
        items=bundled,
        years=YEAR_OPTIONS,
        show_tag_banner=(not my_tags),
        exp=me.exp or 0,
        realm=realm_of(me.exp or 0),
        progress=realm_progress(me.exp or 0),
        profile_locked=profile_locked(me),
        profile_lock_days=profile_lock_days(me),
        notice_n=AdminNotice.query.filter_by(user_id=me.id, is_read=False).count(),
    )


def profile_locked(user):
    """个人资料一个月只能改一次。从未改过（profile_updated_at 为空）时可改。"""
    if not user.profile_updated_at:
        return False
    return now_utc() - user.profile_updated_at < timedelta(days=30)


def profile_lock_days(user):
    """距离下次可修改还剩几天（0 表示可改）。"""
    if not user.profile_updated_at:
        return 0
    delta = timedelta(days=30) - (now_utc() - user.profile_updated_at)
    return max(0, delta.days + (1 if delta.seconds else 0))


@bp.route("/realm")
def realm_page():
    """修炼境界详情：修炼值进度 + 今日修炼进展。"""
    me = current_user()
    progress = realm_progress(me.exp or 0)
    logs, today_total = today_exp_logs(me.id)
    return render_template(
        "realm.html",
        nav="me",
        exp=me.exp or 0,
        progress=progress,
        logs=logs,
        today_total=today_total,
        daily_limit=daily_thought_limit(me.exp or 0),
    )


@bp.route("/realm/rules")
def realm_rules():
    """修炼境界说明：各境界门槛与权力、修炼值获得方法。"""
    me = current_user()
    my_idx = realm_index(me.exp or 0)
    rows = []
    for i, r in enumerate(REALMS):
        rows.append(
            {
                "index": i + 1,
                "name": r["name"],
                "full": f"{r['name']}大佬",
                "threshold": r["threshold"],
                "daily_thoughts": r["daily_thoughts"],
                "invites": r["invites"],
                "mine": i == my_idx,
                "passed": i < my_idx,
            }
        )
    return render_template("realm_rules.html", nav="me", rows=rows, rules=EXP_RULES, my_idx=my_idx)


@bp.route("/me/thoughts")
def my_thoughts():
    """我的随想（个人主页二级页）。"""
    me = current_user()
    items = Thought.query.filter_by(author_id=me.id).order_by(Thought.created_at.desc()).limit(50).all()
    bundled = []
    if items:
        tmap = tags_for_thoughts([t.id for t in items])
        likes_count, liked_ids, comments_count = likes_and_comments_for([t.id for t in items], me.id)
        bundled = [
            serialize_thought(t, me, tmap, likes_count, liked_ids, me, comments_count.get(t.id, 0))
            for t in items
        ]
    return render_template("my_thoughts.html", nav="me", items=bundled, total=len(bundled))


@bp.route("/me/notices")
def notices():
    """管理员通知（删除随想 / 评价时附的理由，以对话形式展示）。"""
    me = current_user()
    from models import AdminNotice

    rows = (
        AdminNotice.query.filter_by(user_id=me.id)
        .order_by(AdminNotice.created_at.desc())
        .all()
    )
    AdminNotice.query.filter_by(user_id=me.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return render_template("notices.html", nav="me", rows=rows)


@bp.route("/me/liked")
def liked_page():
    """被喜欢：向我发过好友请求的人。"""
    me = current_user()
    rows = (
        FriendRequest.query.filter_by(to_user_id=me.id)
        .order_by(FriendRequest.created_at.desc())
        .all()
    )
    seen = {}
    for r in rows:
        if r.from_user_id not in seen:
            seen[r.from_user_id] = r
    users = User.query.filter(User.id.in_(list(seen) or [0])).all()
    cards = []
    for u in users:
        r = seen[u.id]
        brief = user_brief(u, me)
        brief["status"] = {"pending": "待你回应", "accepted": "已加为好友", "rejected": "已拒绝"}.get(
            r.status, r.status
        )
        brief["at"] = relative_time(r.created_at)
        cards.append(brief)
    return render_template("people_list.html", nav="me", title="被喜欢", cards=cards,
                           empty_text="还没有人向你打过招呼")


@bp.route("/me/talked")
def talked_page():
    """聊过的人：有过消息往来的会话对象。"""
    me = current_user()
    convs = Conversation.query.filter(
        (Conversation.user_a_id == me.id) | (Conversation.user_b_id == me.id)
    ).all()
    cards = []
    for c in convs:
        if not Message.query.filter_by(conversation_id=c.id).first():
            continue
        pid = c.user_b_id if c.user_a_id == me.id else c.user_a_id
        u = User.query.get(pid)
        if not u:
            continue
        brief = user_brief(u, me)
        last = (
            Message.query.filter_by(conversation_id=c.id).order_by(Message.id.desc()).first()
        )
        brief["status"] = (last.content[:24] + "…") if last and len(last.content) > 24 else (
            last.content if last else ""
        )
        brief["at"] = relative_time(last.created_at) if last else ""
        cards.append(brief)
    cards.sort(key=lambda x: x.get("at") or "")
    return render_template("people_list.html", nav="me", title="聊过的人", cards=cards,
                           empty_text="还没有和谁聊过天")


@bp.route("/users/<int:uid>")
def user_page(uid):
    me = current_user()
    if uid == me.id:
        return redirect(url_for("profile.me_page"))
    u = User.query.get_or_404(uid)
    their_tags = Tag.query.join(UserTag, UserTag.tag_id == Tag.id).filter(UserTag.user_id == u.id).all()
    friends = are_friends(me.id, uid)
    pending = FriendRequest.query.filter_by(from_user_id=me.id, to_user_id=uid, status="pending").first()
    q = thought_visible_query(me).filter(Thought.author_id == uid).order_by(Thought.created_at.desc()).limit(20)
    items = q.all()
    bundled = []
    if items:
        tmap = tags_for_thoughts([t.id for t in items])
        likes_count, liked_ids, comments_count = likes_and_comments_for([t.id for t in items], me.id)
        bundled = [
            serialize_thought(t, me, tmap, likes_count, liked_ids, u, comments_count.get(t.id, 0)) for t in items
        ]
    return render_template(
        "user.html",
        nav="match",
        person=user_brief(u, me),
        their_tags=their_tags,
        friends=friends,
        pending=bool(pending),
        items=bundled,
        my_tags=Tag.query.join(UserTag, UserTag.tag_id == Tag.id).filter(UserTag.user_id == me.id).all(),
    )


@bp.route("/api/profile", methods=["POST"])
def update_profile():
    """编辑个人资料。一个月只能修改一次。"""
    me = current_user()
    if profile_locked(me):
        msg = f"个人资料一个月只能修改一次，还需等待 {profile_lock_days(me)} 天"
        if request.is_json:
            return jsonify({"ok": False, "error": msg}), 400
        return redirect(url_for("profile.me_page"))
    data = request.get_json(force=True, silent=True) or request.form
    role = data.get("role")
    years = data.get("years")
    changed = False
    if role in ("buyer", "seller") and role != me.role:
        me.role = role
        changed = True
    if years in YEAR_OPTIONS and years != me.years:
        me.years = years
        changed = True
    if changed:
        me.profile_updated_at = now_utc()
    db.session.commit()
    if request.is_json:
        return jsonify({"ok": True, "changed": changed})
    return redirect(url_for("profile.me_page"))


@bp.route("/api/onboard", methods=["POST"])
def save_onboard():
    me = current_user()
    data = request.get_json(force=True, silent=True) or {}
    role = data.get("role")
    years = data.get("years")
    skip_tags = bool(data.get("skip_tags"))
    names = data.get("tags") or []
    if role not in ("buyer", "seller") or years not in YEAR_OPTIONS:
        return jsonify({"ok": False, "error": "请完成身份和年限"}), 400
    me.role = role
    me.years = years
    if skip_tags:
        me.tags_skipped = True
    else:
        if len(names) > MAX_TAGS:
            return jsonify({"ok": False, "error": TAG_LIMIT_MSG}), 400
        UserTag.query.filter_by(user_id=me.id).delete()
        for n in names:
            name = (n.get("name") if isinstance(n, dict) else n) or ""
            name = str(name).strip()
            if not name:
                continue
            kind = "stock" if name in PRESET_STOCKS else "industry"
            if isinstance(n, dict) and n.get("kind") in ("industry", "stock"):
                kind = n["kind"]
            preset = name in PRESET_INDUSTRIES or name in PRESET_STOCKS
            tag = ensure_tag(name, kind=kind, preset=preset)
            db.session.add(UserTag(user_id=me.id, tag_id=tag.id))
        me.tags_skipped = len(names) == 0
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/tags", methods=["POST"])
def save_tags():
    me = current_user()
    data = request.get_json(force=True, silent=True) or {}
    names = data.get("tags") or []
    if len(names) > MAX_TAGS:
        return jsonify({"ok": False, "error": TAG_LIMIT_MSG}), 400
    UserTag.query.filter_by(user_id=me.id).delete()
    for n in names:
        name = (n.get("name") if isinstance(n, dict) else n) or ""
        name = str(name).strip()
        if not name:
            continue
        kind = "stock" if name in PRESET_STOCKS else "industry"
        preset = name in PRESET_INDUSTRIES or name in PRESET_STOCKS
        tag = ensure_tag(name, kind=kind, preset=preset)
        db.session.add(UserTag(user_id=me.id, tag_id=tag.id))
    me.tags_skipped = len(names) == 0
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/tags/catalog")
def catalog():
    q = (request.args.get("q") or "").strip()
    industries = Tag.query.filter_by(kind="industry").order_by(Tag.is_preset.desc(), Tag.id).all()
    stocks = Tag.query.filter_by(kind="stock").order_by(Tag.is_preset.desc(), Tag.id).all()
    if q:
        industries = [t for t in industries if q in t.name]
        stocks = [t for t in stocks if q in t.name]
    return jsonify(
        {
            "industries": [{"id": t.id, "name": t.name} for t in industries],
            "stocks": [{"id": t.id, "name": t.name} for t in stocks],
            "preset_industries": PRESET_INDUSTRIES,
            "preset_stocks": PRESET_STOCKS,
        }
    )


def _request_card(r, other_id, me, mine, tmap, direction):
    u = User.query.get(other_id)
    if not u:
        return None
    tids = [t.id for t in tmap.get(u.id, [])]
    common = [t for t in tmap.get(u.id, []) if t.id in mine]
    return {
        "req": r,
        "user": user_brief(u, me),
        "common": common[:4],
        "pct": overlap_pct(mine, tids),
        "rel": relative_time(r.created_at),
        "direction": direction,  # in=收到的 / out=发出的
    }


@bp.route("/requests")
def requests_page():
    """新的研友：最近收到的 + 发出的好友请求。"""
    me = current_user()
    received = (
        FriendRequest.query.filter_by(to_user_id=me.id, status="pending")
        .order_by(FriendRequest.created_at.desc())
        .all()
    )
    sent = (
        FriendRequest.query.filter_by(from_user_id=me.id, status="pending")
        .order_by(FriendRequest.created_at.desc())
        .all()
    )
    mine = set(tag_ids_of(me.id))
    all_other_ids = [r.from_user_id for r in received] + [r.to_user_id for r in sent]
    tmap = tags_map_for_users(all_other_ids)
    in_cards = [c for c in (_request_card(r, r.from_user_id, me, mine, tmap, "in") for r in received) if c]
    out_cards = [c for c in (_request_card(r, r.to_user_id, me, mine, tmap, "out") for r in sent) if c]
    # 打开本页即视为已读：清空通讯录「新的研友」上的小红点
    FriendRequest.query.filter_by(to_user_id=me.id, status="pending", is_seen=False).update(
        {"is_seen": True}, synchronize_session=False
    )
    db.session.commit()
    return render_template(
        "requests.html",
        nav="chat",
        in_cards=in_cards,
        out_cards=out_cards,
        in_n=len(in_cards),
        out_n=len(out_cards),
    )


@bp.route("/api/requests/<int:rid>/accept", methods=["POST"])
def accept(rid):
    me = current_user()
    req = FriendRequest.query.get_or_404(rid)
    if req.to_user_id != me.id or req.status != "pending":
        return jsonify({"ok": False}), 400
    other = accept_request_logic(me, req)
    u = User.query.get(other)
    return jsonify({"ok": True, "nickname": u.nickname, "user_id": other})


@bp.route("/api/requests/<int:rid>/reject", methods=["POST"])
def reject(rid):
    me = current_user()
    req = FriendRequest.query.get_or_404(rid)
    if req.to_user_id != me.id or req.status != "pending":
        return jsonify({"ok": False}), 400
    req.status = "rejected"
    req.responded_at = now_utc()
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/requests/<int:rid>/cancel", methods=["POST"])
def cancel(rid):
    """撤回自己发出的好友请求。"""
    me = current_user()
    req = FriendRequest.query.get_or_404(rid)
    if req.from_user_id != me.id or req.status != "pending":
        return jsonify({"ok": False, "error": "只能撤回自己发出的待处理请求"}), 400
    db.session.delete(req)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/friends")
def friends_page():
    me = current_user()
    fids = friend_ids(me.id)
    users = User.query.filter(User.id.in_(fids)).all() if fids else []
    last_map = {}
    for uid in fids:
        conv = Conversation.query.filter(
            ((Conversation.user_a_id == me.id) & (Conversation.user_b_id == uid))
            | ((Conversation.user_a_id == uid) & (Conversation.user_b_id == me.id))
        ).first()
        last_map[uid] = conv.last_message_at.timestamp() if conv and conv.last_message_at else 0
    users.sort(key=lambda u: (not is_online(u), -last_map.get(u.id, 0)))
    q = (request.args.get("q") or "").strip()
    if q:
        users = [u for u in users if q in u.nickname]
    # pending_new：还没点开过的新请求（小红点）；pending_n：待处理总数
    pending_new = FriendRequest.query.filter_by(
        to_user_id=me.id, status="pending", is_seen=False
    ).count()
    pending_n = FriendRequest.query.filter_by(to_user_id=me.id, status="pending").count()
    return render_template(
        "friends.html",
        nav="chat",
        friends=[user_brief(u, me) for u in users],
        q=q,
        pending_new=pending_new,
        pending_n=pending_n,
    )
