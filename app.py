"""研友 Demo。本项目为演示用途，不做真实身份认证，不得用于生产环境。"""
from flask import Flask, redirect, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import db
from schema import ensure_columns

app = Flask(__name__)
# 让 Flask 信任 Nginx 传过来的 X-Forwarded-Proto / X-Forwarded-For 等头
# 这样以后接 HTTPS 时，url_for / redirect 会自动生成 https:// 链接
# X-Forwarded-Proto 计数为 1 表示只有一层代理（Nginx）
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.from_object(Config)
db.init_app(app)

from routes import register_blueprints  # noqa: E402
from routes.auth import current_user  # noqa: E402
from schema import ensure_columns  # noqa: E402
from services import avatar_index, PRESET_INDUSTRIES, PRESET_STOCKS  # noqa: E402
from seed import ensure_assets, seed_if_empty  # noqa: E402

register_blueprints(app)
app.jinja_env.globals["avatar_of"] = avatar_index
app.jinja_env.globals["SITE_NAME"] = "研友"
app.jinja_env.globals["DISCLAIMER"] = (
    "本网站仅作为 Demo 演示使用，站内所有内容均为虚拟内容，非真实信息，不构成任何投资建议"
)

# 不需要登录即可访问：登录 / 注册 / 找回密码 / 重置密码
OPEN_ENDPOINTS = {
    "auth.login",
    "auth.register",
    "auth.forgot_password",
    "auth.reset_password",
    "static",
}


@app.before_request
def gate():
    if request.endpoint == "static" or (request.path or "").startswith("/static"):
        return None
    # 管理后台走自己的密码鉴权
    if (request.endpoint or "").startswith("admin.") or (request.path or "").startswith("/admin"):
        return None
    user = current_user()
    if request.endpoint in OPEN_ENDPOINTS:
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
    from models import Conversation, FriendRequest, Message, Tag, UserTag

    user = current_user()
    pending = 0
    my_tags = []
    chat_unread = 0
    new_request = 0
    admin_notice = 0
    if user:
        pending = FriendRequest.query.filter_by(to_user_id=user.id, status="pending").count()
        # 未读的新好友请求：聊天页「通讯录」+ 通讯录页「新的研友」小红点
        new_request = FriendRequest.query.filter_by(
            to_user_id=user.id, status="pending", is_seen=False
        ).count()
        from models import AdminNotice

        admin_notice = AdminNotice.query.filter_by(user_id=user.id, is_read=False).count()
        my_tags = Tag.query.join(UserTag, UserTag.tag_id == Tag.id).filter(UserTag.user_id == user.id).all()
        # 计算所有会话的未读消息总数（对方发给我的、未读）
        friend_convs = (
            db.session.query(Conversation.id)
            .filter(
                db.or_(Conversation.user_a_id == user.id, Conversation.user_b_id == user.id)
            )
            .subquery()
        )
        chat_unread = (
            db.session.query(db.func.count(Message.id))
            .filter(
                Message.conversation_id.in_(friend_convs),
                Message.sender_id != user.id,
                Message.is_read.is_(False),
            )
            .scalar()
            or 0
        )
    return {
        "current_user": user,
        "avatar_index": avatar_index(user.nickname) if user else 0,
        "pending_count": pending,
        "new_request": new_request,
        "admin_notice": admin_notice,
        "chat_unread": chat_unread,
        "preset_industries": PRESET_INDUSTRIES,
        "preset_stocks": PRESET_STOCKS,
        "my_tags": my_tags,
    }


@app.route("/")
def home():
    return redirect(url_for("match.page"))


with app.app_context():
    db.create_all()
    ensure_columns(app, db)
    seed_if_empty()
    ensure_assets()


if __name__ == "__main__":
    import os

    port = int(os.environ.get("PORT", 5000))
    # 生产环境（含 DATABASE_URL）默认关闭 debug；本地开发可设 FLASK_ENV=development 打开
    debug = os.environ.get("FLASK_ENV") == "development" and not os.environ.get("DATABASE_URL")
    app.run(host="0.0.0.0", port=port, debug=debug)
