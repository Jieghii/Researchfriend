from flask import Blueprint, jsonify, render_template, request, session

from extensions import db
from models import FriendRequest, Skip, User
from routes.auth import current_user
from services import add_exp, card_payload, now_utc, recommend_candidates, tag_ids_of

bp = Blueprint("match", __name__)


@bp.route("/match")
def page():
    me = current_user()
    my_tags = tag_ids_of(me.id)
    return render_template("match.html", nav="match", cold=len(my_tags) == 0, skipped_hint=0)


@bp.route("/api/match/batch")
def batch():
    me = current_user()
    offset = int(request.args.get("offset") or 0)
    extra = request.args.get("exclude")
    extra_ids = []
    if extra:
        extra_ids = [int(x) for x in extra.split(",") if x.isdigit()]
    items, total, zero_overlap = recommend_candidates(me, limit=20, offset=offset, extra_exclude=extra_ids)
    cards = [card_payload(me, it) for it in items]
    return jsonify({"cards": cards, "total": total, "zero_overlap": zero_overlap, "offset": offset})


@bp.route("/api/match/skip", methods=["POST"])
def skip():
    me = current_user()
    data = request.get_json(force=True, silent=True) or {}
    uid = int(data.get("user_id") or 0)
    if not uid or uid == me.id:
        return jsonify({"ok": False}), 400
    if not Skip.query.filter_by(user_id=me.id, skipped_user_id=uid).first():
        db.session.add(Skip(user_id=me.id, skipped_user_id=uid))
        db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/match/greet", methods=["POST"])
def greet():
    me = current_user()
    data = request.get_json(force=True, silent=True) or {}
    uid = int(data.get("user_id") or 0)
    text = (data.get("greeting") or "").strip()
    if not uid or uid == me.id:
        return jsonify({"ok": False, "error": "没发出去，再试一次？"}), 400
    if not text:
        return jsonify({"ok": False, "error": "先写一句话再发送"}), 400
    if len(text) > 100:
        return jsonify({"ok": False, "error": "招呼语最多 100 字"}), 400
    if FriendRequest.query.filter_by(from_user_id=me.id, to_user_id=uid, status="pending").first():
        return jsonify({"ok": False, "error": "请求已发送"}), 400
    db.session.add(
        FriendRequest(from_user_id=me.id, to_user_id=uid, greeting=text, status="pending", created_at=now_utc())
    )
    # 被别人标注为喜欢：接收方 +3 修炼值
    target = User.query.get(uid)
    if target:
        add_exp(target, "liked", ref_id=me.id, desc="被标注为喜欢")
    db.session.commit()
    return jsonify({"ok": True})
