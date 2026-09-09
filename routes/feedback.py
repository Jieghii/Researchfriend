"""用户反馈。"""

from flask import Blueprint, jsonify, render_template, request

from extensions import db
from models import Feedback
from routes.auth import current_user
from services import relative_time

bp = Blueprint("feedback", __name__)


@bp.route("/feedback")
def page():
    me = current_user()
    items = (
        Feedback.query.filter_by(user_id=me.id)
        .order_by(Feedback.created_at.desc())
        .limit(20)
        .all()
    )
    view = [
        {
            "id": f.id,
            "content": f.content,
            "status": f.status,
            "admin_note": f.admin_note,
            "time": relative_time(f.created_at),
        }
        for f in items
    ]
    return render_template("feedback.html", nav="discover", items=view)


@bp.route("/api/feedback", methods=["POST"])
def submit():
    me = current_user()
    data = request.get_json(force=True, silent=True) or {}
    content = (data.get("content") or "").strip()
    contact = (data.get("contact") or "").strip()[:64]
    if not content:
        return jsonify({"ok": False, "error": "先写点什么再提交"}), 400
    if len(content) > 500:
        return jsonify({"ok": False, "error": "反馈最多 500 字"}), 400
    rec = Feedback(user_id=me.id, content=content, contact=contact)
    db.session.add(rec)
    db.session.commit()
    return jsonify({"ok": True, "message": "收到啦，谢谢你！"})
