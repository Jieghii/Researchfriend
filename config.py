"""应用配置。DATABASE_URL 有值走 Postgres（Neon），否则走本地 SQLite。此处是唯一分支。"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _database_uri() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if "sslmode=" not in url:
            url += ("&" if "?" in url else "?") + "sslmode=require"
        return url
    return "sqlite:///" + (BASE_DIR / "yantou.db").as_posix()


def _secret_key() -> str:
    """生产环境（有 DATABASE_URL）必须显式配置 SECRET_KEY，绝不退回固定值。
    本地开发未配置时随机生成一个临时密钥，重启后会话失效，不影响开发。"""
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    if os.environ.get("DATABASE_URL"):
        raise RuntimeError(
            "生产环境必须在环境变量中配置 SECRET_KEY，禁止使用默认密钥。"
        )
    return secrets.token_hex(32)


class Config:
    SECRET_KEY = _secret_key()
    # 管理后台密码（/admin）。生产环境请务必在 Vercel 改为自己的密码。
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "yanyou-admin-2026"
    ADMIN_IS_DEFAULT = not os.environ.get("ADMIN_PASSWORD")
    # 邮件配置：全部填齐则密码重置链接会真的发到邮箱；否则走演示模式（链接直接显示在页面上）
    MAIL_SERVER = os.environ.get("MAIL_SERVER") or ""
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 465)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME") or ""
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD") or ""
    MAIL_FROM = os.environ.get("MAIL_FROM") or (os.environ.get("MAIL_USERNAME") or "")
    MAIL_USE_SSL = (os.environ.get("MAIL_USE_SSL") or "1") == "1"
    MAIL_ENABLED = bool(MAIL_SERVER and MAIL_USERNAME and MAIL_PASSWORD and MAIL_FROM)
    # 邀请码默认额度
    INVITE_MAX_USES = int(os.environ.get("INVITE_MAX_USES") or 5)
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Secure Cookie 只在 HTTPS 环境下生效。仅当显式设置 PROXIED_HTTPS=1 才打开。
    # 默认 False 是为了 HTTP 部署也能登录；以后接域名 + 配置 Nginx HTTPS 后
    # 在环境变量里加 PROXIED_HTTPS=1 即可自动启用。
    SESSION_COOKIE_SECURE = os.environ.get("PROXIED_HTTPS") == "1"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 12
    # 演示用途：不做真实身份认证，不得直接用于生产环境。
