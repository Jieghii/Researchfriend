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
    are_friends,
    avatar_index,
    ensure_tag,
    friend_ids,
    is_online,
    now_utc,
    overlap_pct,
    pair_ids,
    relative_active,
    serialize_thought,
    tag_ids_of,
    tags_for_thoughts,
    tags_map_for_users,
    thought_visible_query,
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
    return render_template(
        "me.html",
        nav="me",
        liked=liked,
        talked=talked,
        thoughts_n=thoughts_n,
        pending_n=pending_n,
        my_tags=my_tags,
        friends=friends[:8],
        friends_n=len(friends),
        items=bundled,
        years=YEAR_OPTIONS,
        show_tag_banner=(not my_tags),
    )


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
    me = current_user()
    data = request.get_json(force=True, silent=True) or request.form
    role = data.get("role")
    years = data.get("years")
    if role in ("buyer", "seller"):
        me.role = role
    if years in YEAR_OPTIONS:
        me.years = years
    db.session.commit()
    if request.is_json:
        return jsonify({"ok": True})
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


@bp.route("/requests")
def requests_page():
    me = current_user()
    rows = (
        FriendRequest.query.filter_by(to_user_id=me.id, status="pending")
        .order_by(FriendRequest.created_at.desc())
        .all()
    )
    from_ids = [r.from_user_id for r in rows]
    users = {u.id: u for u in User.query.filter(User.id.in_(from_ids or [0])).all()}
    mine = set(tag_ids_of(me.id))
    tmap = tags_map_for_users(from_ids)
    cards = []
    for r in rows:
        u = users[r.from_user_id]
        tids = [t.id for t in tmap.get(u.id, [])]
        common = [t for t in tmap.get(u.id, []) if t.id in mine]
        cards.append(
            {
                "req": r,
                "user": user_brief(u, me),
                "common": common[:4],
                "pct": overlap_pct(mine, tids),
                "rel": __import__("services").relative_time(r.created_at),
            }
        )
    return render_template("requests.html", nav="me", cards=cards)


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
    return render_template("friends.html", nav="me", friends=[user_brief(u, me) for u in users], q=q)
