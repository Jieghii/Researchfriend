"""研投圈 Demo。本项目为演示用途，不做真实身份认证，不得用于生产环境。"""
from flask import Flask, redirect, request, session, url_for

from config import Config
from extensions import db

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

from routes import register_blueprints  # noqa: E402
from routes.auth import current_user  # noqa: E402
from services import avatar_index, PRESET_INDUSTRIES, PRESET_STOCKS  # noqa: E402
from seed import seed_if_empty  # noqa: E402

register_blueprints(app)
app.jinja_env.globals["avatar_of"] = avatar_index

OPEN_ENDPOINTS = {"auth.login", "static"}


@app.before_request
def gate():
    if request.endpoint == "static" or (request.path or "").startswith("/static"):
        return None
    user = current_user()
    if request.endpoint in ("auth.login",):
        return None
    if not user:
        if request.path.startswith("/api/"):
            return {"ok": False, "error": "未登录"}, 401
        return redirect(url_for("auth.login"))
    if request.endpoint in ("auth.onboard", "profile.save_onboard", "auth.logout", "auth.heartbeat"):
        return None
    if not user.role or not user.years:
        if request.path.startswith("/api/"):
            return {"ok": False, "error": "请先完成资料"}, 403
        return redirect(url_for("auth.onboard"))
    return None


@app.context_processor
def inject_globals():
    user = current_user()
    pending = 0
    my_tags = []
    if user:
        from models import FriendRequest, Tag, UserTag

        pending = FriendRequest.query.filter_by(to_user_id=user.id, status="pending").count()
        my_tags = Tag.query.join(UserTag, UserTag.tag_id == Tag.id).filter(UserTag.user_id == user.id).all()
    return {
        "current_user": user,
        "avatar_index": avatar_index(user.nickname) if user else 0,
        "pending_count": pending,
        "preset_industries": PRESET_INDUSTRIES,
        "preset_stocks": PRESET_STOCKS,
        "my_tags": my_tags,
    }


@app.route("/")
def home():
    return redirect(url_for("match.page"))


with app.app_context():
    db.create_all()
    seed_if_empty()


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
