"""邮件发送（用于找回密码）。

设计：配置齐全时真发邮件；未配置时返回 (False, 原因)，调用方降级为"演示模式"
——把重置链接直接显示在页面上，保证找回密码的完整流程始终可走通。
"""

import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

from flask import current_app


def mail_enabled() -> bool:
    return bool(current_app.config.get("MAIL_ENABLED"))


def send_reset_email(to_email: str, reset_link: str, nickname: str):
    """发送密码重置邮件。返回 (是否发送成功, 说明)。"""
    cfg = current_app.config
    if not cfg.get("MAIL_ENABLED"):
        return False, "未配置邮件服务，已切换为演示模式"

    subject = "研友 · 重置密码"
    body = (
        f"{nickname}，你好：\n\n"
        f"我们收到了重置密码的请求。请点击下面的链接设置新密码（2 小时内有效）：\n\n"
        f"{reset_link}\n\n"
        f"如果不是你本人操作，忽略这封邮件即可，密码不会改变。\n\n"
        f"—— 研友（Demo 演示站点）"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr(("研友", cfg.get("MAIL_FROM")))
    msg["To"] = to_email

    try:
        if cfg.get("MAIL_USE_SSL"):
            server = smtplib.SMTP_SSL(cfg.get("MAIL_SERVER"), cfg.get("MAIL_PORT"), timeout=20)
        else:
            server = smtplib.SMTP(cfg.get("MAIL_SERVER"), cfg.get("MAIL_PORT"), timeout=20)
            server.starttls()
        with server:
            server.login(cfg.get("MAIL_USERNAME"), cfg.get("MAIL_PASSWORD"))
            server.sendmail(cfg.get("MAIL_FROM"), [to_email], msg.as_string())
        return True, "邮件已发送"
    except Exception as exc:
        return False, f"邮件发送失败：{exc}"
