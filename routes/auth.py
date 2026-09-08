from datetime import datetime
import re

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import User
from services import YEAR_OPTIONS, now_utc

bp = Blueprint("auth", __name__)


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return User.query.get(uid)


def login_required_user():
    return current_user()


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        u = current_user()
        if not u.role or not u.years:
            return redirect(url_for("auth.onboard"))
        return redirect(url_for("match.page"))
    error = None
    if request.method == "POST":
        nickname = (request.form.get("nickname") or "").strip()
        password = request.form.get("password") or ""
        if not nickname or not password:
            error = "昵称和密码都要填哦"
        elif " " in nickname or len(nickname) > 16:
            error = "昵称最多 16 个字，不能有空格"
        elif len(nickname) < 2:
            error = "昵称至少 2 个字"
        elif len(password) < 6:
            error = "密码至少 6 位"
        else:
            user = User.query.filter_by(nickname=nickname).first()
            if user:
                if not check_password_hash(user.password_hash, password):
                    error = "密码不对，再试一次？"
                else:
                    session.clear()
                    session["uid"] = user.id
                    session.permanent = False
                    user.last_active_at = now_utc()
                    db.session.commit()
                    if not user.role or not user.years:
                        return redirect(url_for("auth.onboard"))
                    return redirect(url_for("match.page"))
            else:
                user = User(
                    nickname=nickname,
                    password_hash=generate_password_hash(password, method="pbkdf2:sha256"),
                    last_active_at=now_utc(),
                )
                db.session.add(user)
                db.session.commit()
                session.clear()
                session["uid"] = user.id
                session.permanent = False
                return redirect(url_for("auth.onboard"))
    return render_template("login.html", error=error, form=request.form)


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
