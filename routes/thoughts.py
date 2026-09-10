from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func

from extensions import db
from models import Comment, Like, Tag, Thought, ThoughtTag, User
from routes.auth import current_user
from services import (
    PRESET_INDUSTRIES,
    PRESET_STOCKS,
    add_exp,
    daily_thought_limit,
    ensure_tag,
    likes_and_comments_for,
    now_utc,
    realm_of,
    serialize_thought,
    tags_for_thoughts,
    thought_visible_query,
    thought_visible_to,
    today_thought_count,
    user_brief,
)

bp = Blueprint("thoughts", __name__)

SORT_OPTIONS = (
    ("new", "最新发布"),
    ("commented", "最新评论"),
    ("comments", "最多评论"),
    ("likes", "最多点赞"),
)
SORT_KEYS = {k for k, _ in SORT_OPTIONS}


def _page_items(me, scope="all", tag_id=None, page=1, sort="new"):
    q = thought_visible_query(me)
    if scope == "mine":
        q = Thought.query.filter_by(author_id=me.id)
    if tag_id:
        q = q.join(ThoughtTag, ThoughtTag.thought_id == Thought.id).filter(ThoughtTag.tag_id == tag_id)
    if sort == "likes":
        like_sub = (
            db.session.query(Like.thought_id, func.count(Like.id).label("n"))
            .group_by(Like.thought_id)
            .subquery()
        )
        q = q.outerjoin(like_sub, like_sub.c.thought_id == Thought.id).order_by(
            func.coalesce(like_sub.c.n, 0).desc(), Thought.created_at.desc()
        )
    elif sort == "comments":
        c_sub = (
            db.session.query(Comment.thought_id, func.count(Comment.id).label("n"))
            .group_by(Comment.thought_id)
            .subquery()
        )
        q = q.outerjoin(c_sub, c_sub.c.thought_id == Thought.id).order_by(
            func.coalesce(c_sub.c.n, 0).desc(), Thought.created_at.desc()
        )
    elif sort == "commented":
        last_sub = (
            db.session.query(Comment.thought_id, func.max(Comment.created_at).label("last_at"))
            .group_by(Comment.thought_id)
            .subquery()
        )
        q = q.outerjoin(last_sub, last_sub.c.thought_id == Thought.id).order_by(
            last_sub.c.last_at.is_(None),
            last_sub.c.last_at.desc(),
            Thought.created_at.desc(),
        )
    else:
        q = q.order_by(Thought.created_at.desc())
    items = q.offset((page - 1) * 10).limit(11).all()
    has_more = len(items) > 10
    items = items[:10]
    return items, has_more


def _bundle(me, items):
    ids = [t.id for t in items]
    authors = {u.id: u for u in User.query.filter(User.id.in_({t.author_id for t in items} or {0})).all()}
    tmap = tags_for_thoughts(ids)
    likes_count, liked_ids, comments_count = likes_and_comments_for(ids, me.id)
    return [
        serialize_thought(
            t,
            me,
            tmap,
            likes_count,
            liked_ids,
            authors[t.author_id],
            comments_count.get(t.id, 0),
        )
        for t in items
    ]


@bp.route("/thoughts")
def timeline():
    me = current_user()
    scope = request.args.get("scope") or "all"
    if scope == "following":
        scope = "all"
    tag_id = request.args.get("tag", type=int)
    tag = Tag.query.get(tag_id) if tag_id else None
    sort = request.args.get("sort") or "new"
    if sort not in SORT_KEYS:
        sort = "new"
    items, has_more = _page_items(me, scope, tag_id, 1, sort)
    return render_template(
        "thoughts.html",
        nav="discover",
        items=_bundle(me, items),
        has_more=has_more,
        scope=scope,
        tag=tag,
        sort=sort,
        sort_options=SORT_OPTIONS,
    )


@bp.route("/api/thoughts")
def api_list():
    me = current_user()
    scope = request.args.get("scope") or "all"
    tag_id = request.args.get("tag", type=int)
    page = int(request.args.get("page") or 1)
    sort = request.args.get("sort") or "new"
    if sort not in SORT_KEYS:
        sort = "new"
    items, has_more = _page_items(me, scope, tag_id, page, sort)
    return jsonify({"items": _bundle(me, items), "has_more": has_more, "page": page})


@bp.route("/api/thoughts", methods=["POST"])
def create():
    me = current_user()
    data = request.get_json(force=True, silent=True) or {}
    body = (data.get("body") or "").strip()
    vis = data.get("visibility") or "public"
    if vis not in ("public", "friends", "self"):
        vis = "public"
    if not body:
        return jsonify({"ok": False, "error": "发布失败，再试一次？"}), 400
    if len(body) > 500:
        return jsonify({"ok": False, "error": "最多 500 字"}), 400
    # 每日发布额度由境界决定
    limit = daily_thought_limit(me.exp or 0)
    if today_thought_count(me.id) >= limit:
        realm = realm_of(me.exp or 0)
        return jsonify(
            {
                "ok": False,
                "error": f"今日额度已用完：{realm['full']}每天可发 {limit} 条随想，提升境界可增加额度",
            }
        ), 400
    th = Thought(author_id=me.id, body=body, visibility=vis, created_at=now_utc())
    db.session.add(th)
    db.session.flush()
    linked = set()
    for tid in data.get("tag_ids") or []:
        tag = Tag.query.get(int(tid))
        if tag and tag.id not in linked:
            db.session.add(ThoughtTag(thought_id=th.id, tag_id=tag.id))
            linked.add(tag.id)
    # 自定义标签：用户可直接输入任意话题名，不存在则自动创建
    for raw in data.get("tag_names") or []:
        name = str(raw).strip().lstrip("#").strip()
        if not name or len(name) > 16:
            continue
        if name in PRESET_STOCKS:
            kind = "stock"
        else:
            kind = "industry"
        preset = name in PRESET_INDUSTRIES or name in PRESET_STOCKS
        tag = ensure_tag(name, kind=kind, preset=preset)
        if tag.id not in linked:
            db.session.add(ThoughtTag(thought_id=th.id, tag_id=tag.id))
            linked.add(tag.id)
    # 发布随想 +1 修炼值
    add_exp(me, "thought", ref_id=th.id, desc="发布随想")
    db.session.commit()
    packed = _bundle(me, [th])[0]
    return jsonify({"ok": True, "item": packed})


@bp.route("/thoughts/<int:tid>")
def detail(tid):
    me = current_user()
    th = Thought.query.get_or_404(tid)
    if not thought_visible_to(th, me):
        return render_template("thought_detail.html", nav="discover", missing=True), 404
    author = User.query.get(th.author_id)
    tmap = tags_for_thoughts([th.id])
    likes_count, liked_ids, comments_count = likes_and_comments_for([th.id], me.id)
    item = serialize_thought(th, me, tmap, likes_count, liked_ids, author, comments_count.get(th.id, 0))
    likers = (
        User.query.join(Like, Like.user_id == User.id).filter(Like.thought_id == th.id).limit(8).all()
    )
    comments = Comment.query.filter_by(thought_id=th.id).order_by(Comment.created_at.asc()).all()
    c_authors = {u.id: u for u in User.query.filter(User.id.in_({c.author_id for c in comments} or {0})).all()}
    focus = request.args.get("focus") == "1"
    return render_template(
        "thought_detail.html",
        nav="discover",
        missing=False,
        item=item,
        likers=[user_brief(u) for u in likers],
        like_total=likes_count.get(th.id, 0),
        comments=[
            {
                "id": c.id,
                "content": c.content,
                "rel_time": __import__("services").relative_time(c.created_at),
                "mine": c.author_id == me.id,
                "author": user_brief(c_authors[c.author_id]),
            }
            for c in comments
        ],
        focus=focus,
    )


@bp.route("/api/thoughts/<int:tid>/like", methods=["POST"])
def like(tid):
    me = current_user()
    th = Thought.query.get_or_404(tid)
    if not thought_visible_to(th, me):
        return jsonify({"ok": False}), 404
    existing = Like.query.filter_by(user_id=me.id, thought_id=tid).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        liked = False
    else:
        db.session.add(Like(user_id=me.id, thought_id=tid))
        # 随想被点赞：作者 +2 修炼值（同一条随想只记一次）
        author = User.query.get(th.author_id)
        if author and author.id != me.id:
            from models import ExpLog

            dup = ExpLog.query.filter_by(user_id=author.id, kind="like", ref_id=tid).first()
            if not dup:
                add_exp(author, "like", ref_id=tid, desc="随想被点赞")
        db.session.commit()
        liked = True
    n = Like.query.filter_by(thought_id=tid).count()
    return jsonify({"ok": True, "liked": liked, "likes": n})


@bp.route("/api/thoughts/<int:tid>/comments", methods=["POST"])
def comment(tid):
    me = current_user()
    th = Thought.query.get_or_404(tid)
    if not thought_visible_to(th, me):
        return jsonify({"ok": False}), 404
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("content") or "").strip()
    if not text:
        return jsonify({"ok": False}), 400
    c = Comment(thought_id=tid, author_id=me.id, content=text[:300], created_at=now_utc())
    db.session.add(c)
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "comment": {
                "id": c.id,
                "content": c.content,
                "rel_time": "刚刚",
                "mine": True,
                "author": user_brief(me),
            },
        }
    )


@bp.route("/api/thoughts/<int:tid>", methods=["DELETE"])
def delete_thought(tid):
    me = current_user()
    th = Thought.query.get_or_404(tid)
    if th.author_id != me.id:
        return jsonify({"ok": False}), 403
    Like.query.filter_by(thought_id=tid).delete()
    Comment.query.filter_by(thought_id=tid).delete()
    ThoughtTag.query.filter_by(thought_id=tid).delete()
    db.session.delete(th)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/comments/<int:cid>", methods=["DELETE"])
def delete_comment(cid):
    me = current_user()
    c = Comment.query.get_or_404(cid)
    if c.author_id != me.id:
        return jsonify({"ok": False}), 403
    db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True})
