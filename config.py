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
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # 生产环境（有 DATABASE_URL，即 HTTPS）下强制 Secure Cookie
    SESSION_COOKIE_SECURE = bool(os.environ.get("DATABASE_URL"))
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 12
    # 演示用途：不做真实身份认证，不得直接用于生产环境。
