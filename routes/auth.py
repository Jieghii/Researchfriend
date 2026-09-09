import re
from datetime import datetime, timedelta

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from codes import gen_invite_code
from extensions import db
from mailer import send_reset_email
from models import InviteCode, PasswordResetToken, User
from services import YEAR_OPTIONS, now_utc

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return User.query.get(uid)


def login_required_user():
    return current_user()


def _valid_nickname(nickname):
    if len(nickname) < 2:
        return "昵称至少 2 个字"
    if len(nickname) > 16:
        return "昵称最多 16 个字"
    if " " in nickname:
        return "昵称不能有空格"
    return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        u = current_user()
        if not u.role or not u.years:
            return redirect(url_for("auth.onboard"))
        return redirect(url_for("match.page"))

    error = None
    mode = None  # no_user / bad_pw / banned
    if request.method == "POST":
        nickname = (request.form.get("nickname") or "").strip()
        password = request.form.get("password") or ""

        err = _valid_nickname(nickname)
        if err:
            error = err
        elif not password:
            error = "请填写密码"
        else:
            user = User.query.filter_by(nickname=nickname).first()
            if not user:
                error = "这个昵称还没有注册过，先去注册一个吧"
                mode = "no_user"
            elif user.is_banned:
                error = "该账号已被停用，如有疑问请通过「用户反馈」联系我们"
                mode = "banned"
            elif not check_password_hash(user.password_hash, password):
                error = "密码不对，再试一次？"
                mode = "bad_pw"
            else:
                session.clear()
                session["uid"] = user.id
                session.permanent = False
                user.last_active_at = now_utc()
                db.session.commit()
                if not user.role or not user.years:
                    return redirect(url_for("auth.onboard"))
                return redirect(url_for("match.page"))

    return render_template("login.html", error=error, mode=mode, form=request.form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("match.page"))

    error = None
    if request.method == "POST":
        nickname = (request.form.get("nickname") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        email = (request.form.get("email") or "").strip()
        code = (request.form.get("invite_code") or "").strip().upper()

        err = _valid_nickname(nickname)
        if err:
            error = err
        elif len(password) < 6:
            error = "密码至少 6 位"
        elif password != confirm:
            error = "两次输入的密码不一致"
        elif email and not EMAIL_RE.match(email):
            error = "邮箱格式不太对，检查一下？"
        elif email and User.query.filter_by(email=email).first():
            error = "这个邮箱已经被使用了"
        elif not code:
            error = "请填写邀请码"
        else:
            invite = InviteCode.query.filter_by(code=code).first()
            if not invite:
                error = "邀请码不存在"
            elif not invite.is_active:
                error = "该邀请码已被停用"
            elif invite.is_full:
                error = f"该邀请码的 {invite.max_uses} 个名额已用完"
            elif User.query.filter_by(nickname=nickname).first():
                error = "这个昵称已经被用了"
            else:
                user = User(
                    nickname=nickname,
                    password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
                    email=email or None,
                    invite_code_id=invite.id,
                    last_active_at=now_utc(),
                )
                db.session.add(user)
                db.session.flush()
                # 注册即拥有自己的邀请码，额度 5 人
                own = InviteCode(
                    code=gen_invite_code(exists=lambda c: InviteCode.query.filter_by(code=c).first()),
                    owner_user_id=user.id,
                    max_uses=5,
                )
                db.session.add(own)
                db.session.commit()
                session.clear()
                session["uid"] = user.id
                session.permanent = False
                return redirect(url_for("auth.onboard"))

    return render_template("register.html", error=error, form=request.form)


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    error = None
    notice = None
    demo_link = None
    mail_tip = None

    if request.method == "POST":
        account = (request.form.get("account") or "").strip()
        user = None
        if EMAIL_RE.match(account):
            user = User.query.filter_by(email=account).first()
        else:
            user = User.query.filter_by(nickname=account).first()

        if not user:
            error = "没有找到这个账号，检查一下昵称或邮箱？"
        elif not user.email:
            error = "这个账号没有绑定邮箱，无法通过邮箱找回密码"
        else:
            token = gen_invite_code(32, exists=lambda t: PasswordResetToken.query.filter_by(token=t).first())
            rec = PasswordResetToken(
                token=token,
                user_id=user.id,
                expires_at=datetime.utcnow() + timedelta(hours=2),
            )
            db.session.add(rec)
            db.session.commit()
            link = url_for("auth.reset_password", token=token, _external=True)
            sent, mail_tip = send_reset_email(user.email, link, user.nickname)
            if sent:
                notice = f"重置链接已发送到 {_mask_email(user.email)}，2 小时内有效"
            else:
                demo_link = link
                notice = "邮件服务未开启，已切换为演示模式：请直接复制下面的链接重置密码"

    return render_template(
        "forgot_password.html",
        error=error,
        notice=notice,
        demo_link=demo_link,
        mail_tip=mail_tip,
        form=request.form,
    )


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    rec = PasswordResetToken.query.filter_by(token=token).first()
    error = None
    done = False

    if not rec or rec.used or rec.expires_at < datetime.utcnow():
        # 已登录用户点开失效链接时，不要显示空白页，回个人主页
        if current_user():
            return redirect(url_for("profile.me_page"))
        return render_template("reset_password.html", invalid=True)

    # 链接有效：先退出当前登录态，保证重置页能正常展示
    if current_user():
        session.clear()

    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        if len(password) < 6:
            error = "密码至少 6 位"
        elif password != confirm:
            error = "两次输入的密码不一致"
        else:
            user = User.query.get(rec.user_id)
            user.password_hash = generate_password_hash(password, method="pbkdf2:sha256")
            rec.used = True
            db.session.commit()
            done = True

    return render_template("reset_password.html", invalid=False, error=error, done=done)


@bp.route("/onboard", methods=["GET", "POST"])
def onboard():
    user = current_user()
    if not user:
        return redirect(url_for("auth.login"))
    if user.role and user.years and request.method == "GET" and request.args.get("force") != "1":
        return redirect(url_for("match.page"))
    return render_template("onboard.html", years=YEAR_OPTIONS)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    user = current_user()
    if not user:
        return jsonify({"ok": False}), 401
    user.last_active_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "邮箱"
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        masked = name[0] + "*"
    else:
        masked = name[0] + "*" * (len(name) - 2) + name[-1]
    return f"{masked}@{domain}"
