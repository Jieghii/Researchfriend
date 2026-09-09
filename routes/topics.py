from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from extensions import db
from models import Tag, Thought, ThoughtTag, User, UserTag
from routes.auth import current_user
from services import (
    PRESET_INDUSTRIES,
    PRESET_STOCKS,
    card_payload,
    MAX_TAGS,
    TAG_LIMIT_MSG,
    ensure_tag,
    excluded_user_ids,
    get_or_create_conversation,
    is_online,
    overlap_pct,
    recompute_hot_ranks,
    relative_active,
    tag_ids_of,
    tags_for_thoughts,
    tags_map_for_users,
    thought_visible_query,
    user_brief,
    avatar_index,
)

bp = Blueprint("topics", __name__)


@bp.route("/topics")
def square():
    me = current_user()
    hot = recompute_hot_ranks()
    my_tags = (
        Tag.query.join(UserTag, UserTag.tag_id == Tag.id).filter(UserTag.user_id == me.id).all()
    )
    industries = Tag.query.filter_by(kind="industry", is_preset=True).order_by(Tag.id).all()
    stocks = Tag.query.filter_by(kind="stock", is_preset=True).order_by(Tag.id).all()
    return render_template(
        "topics.html",
        nav="discover",
        hot=hot,
        my_tags=my_tags,
        industries=industries or [type("T", (), {"id": 0, "name": n}) for n in PRESET_INDUSTRIES],
        stocks=stocks or [type("T", (), {"id": 0, "name": n}) for n in PRESET_STOCKS],
    )


@bp.route("/api/topics/search")
def search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"items": []})
    tags = Tag.query.filter(Tag.name.contains(q)).limit(12).all()
    return jsonify({"items": [{"id": t.id, "name": t.name, "kind": t.kind} for t in tags]})


@bp.route("/api/topics/create", methods=["POST"])
def create_topic():
    me = current_user()
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "先写话题名"}), 400
    if len(name) > 32:
        return jsonify({"ok": False, "error": "话题名太长了"}), 400
    tag = ensure_tag(name, kind="industry", preset=False)
    linked = UserTag.query.filter_by(user_id=me.id, tag_id=tag.id).first()
    if not linked:
        count = UserTag.query.filter_by(user_id=me.id).count()
        if count >= MAX_TAGS:
            db.session.commit()
            return jsonify({"ok": True, "id": tag.id, "added": False, "error": TAG_LIMIT_MSG})
        db.session.add(UserTag(user_id=me.id, tag_id=tag.id))
    db.session.commit()
    return jsonify({"ok": True, "id": tag.id, "added": True})


@bp.route("/topics/<int:tag_id>")
def detail(tag_id):
    me = current_user()
    tag = Tag.query.get_or_404(tag_id)
    followers = UserTag.query.filter_by(tag_id=tag_id).count()
    rows = UserTag.query.filter(UserTag.tag_id == tag_id, UserTag.user_id != me.id).all()
    user_ids = [r.user_id for r in rows]
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    my_tags = set(tag_ids_of(me.id))
    tmap = tags_map_for_users([u.id for u in users])
    people = []
    for u in users:
        tids = [t.id for t in tmap.get(u.id, [])]
        people.append(
            {
                "user": u,
                "brief": user_brief(u, me),
                "pct": overlap_pct(my_tags, tids),
                "online": is_online(u),
                "has_common": len(my_tags & set(tids)) > 0,
            }
        )
    people.sort(key=lambda x: (not x["online"], not x["has_common"], -(x["pct"] or -1)))
    related_q = (
        thought_visible_query(me)
        .join(ThoughtTag, ThoughtTag.thought_id == Thought.id)
        .filter(ThoughtTag.tag_id == tag_id, Thought.visibility == "public")
        .order_by(Thought.created_at.desc())
        .limit(3)
    )
    related = related_q.all()
    authors = {u.id: u for u in User.query.filter(User.id.in_({t.author_id for t in related} or {0})).all()}
    ttags = tags_for_thoughts([t.id for t in related])
    related_view = [
        {"thought": th, "author": authors.get(th.author_id), "tags": ttags.get(th.id, [])} for th in related
    ]
    only_me = followers <= 1 and (UserTag.query.filter_by(user_id=me.id, tag_id=tag_id).first() is not None or followers == 0)
    if followers == 0:
        only_me = True
    elif UserTag.query.filter(UserTag.tag_id == tag_id, UserTag.user_id != me.id).count() == 0:
        only_me = True
    else:
        only_me = False
    return render_template(
        "topic_detail.html",
        nav="discover",
        tag=tag,
        followers=followers,
        people=people,
        related=related_view,
        only_me=only_me,
    )


@bp.route("/api/topics/<int:tag_id>/match", methods=["POST"])
def system_match(tag_id):
    me = current_user()
    excluded = excluded_user_ids(me.id)
    rows = UserTag.query.filter(UserTag.tag_id == tag_id, UserTag.user_id.notin_(excluded)).all()
    ids = [r.user_id for r in rows]
    if not ids:
        return jsonify({"ok": False, "empty": True})
    users = User.query.filter(User.id.in_(ids)).all()
    my_tags = set(tag_ids_of(me.id))
    tmap = tags_map_for_users(ids)
    scored = []
    for u in users:
        tids = [t.id for t in tmap.get(u.id, [])]
        scored.append((is_online(u), overlap_pct(my_tags, tids) or -1, u))
    scored.sort(key=lambda x: (not x[0], -x[1], -(x[2].last_active_at.timestamp() if x[2].last_active_at else 0)))
    peer = scored[0][2]
    conv = get_or_create_conversation(me.id, peer.id, source_tag_id=tag_id)
    return jsonify({"ok": True, "user_id": peer.id, "conversation_id": conv.id})
