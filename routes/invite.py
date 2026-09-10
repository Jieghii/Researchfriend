"""邀请码页面：我的专属邀请码与邀请链接、额度与使用情况、我是被谁邀请的。"""

from flask import Blueprint, render_template, request, url_for

from extensions import db
from models import InviteCode, User
from routes.auth import current_user
from services import invite_quota

bp = Blueprint("invite", __name__)


def ensure_my_codes(user):
    """确保用户拥有与其境界匹配的邀请码数量（闻弦境 1 个，每升一境 +1）。"""
    from codes import gen_invite_code

    need = invite_quota(user.exp or 0)
    codes = InviteCode.query.filter_by(owner_user_id=user.id).order_by(InviteCode.id).all()
    while len(codes) < need:
        code = InviteCode(
            code=gen_invite_code(exists=lambda c: InviteCode.query.filter_by(code=c).first()),
            owner_user_id=user.id,
            max_uses=5,
        )
        db.session.add(code)
        db.session.flush()
        codes.append(code)
    if len(codes) != need or any(c.id is None for c in codes):
        db.session.commit()
    return codes


def ensure_my_code(user):
    """兼容旧调用：返回第一张邀请码。"""
    codes = ensure_my_codes(user)
    return codes[0] if codes else None


@bp.route("/invite")
def page():
    me = current_user()
    codes = ensure_my_codes(me)
    quota = invite_quota(me.exp or 0)

    invited_by = None
    if me.invite_code_id:
        used = InviteCode.query.get(me.invite_code_id)
        if used:
            owner = User.query.get(used.owner_user_id) if used.owner_user_id else None
            invited_by = {
                "code": used.code,
                "owner": owner.nickname if owner else "官方邀请码",
            }

    code_cards = []
    for c in codes:
        invited_users = c.invited_users
        used_n = len(invited_users)
        slots = []
        for i in range(c.max_uses):
            if i < used_n:
                u = invited_users[i]
                slots.append({"used": True, "nickname": u.nickname, "at": u.created_at})
            else:
                slots.append({"used": False, "nickname": None, "at": None})
        code_cards.append(
            {
                "code": c,
                "slots": slots,
                "used": used_n,
                "left": max(0, c.max_uses - used_n),
                "link": url_for("auth.register", code=c.code, _external=True),
            }
        )

    return render_template(
        "invite.html",
        nav="me",
        code_cards=code_cards,
        quota=quota,
        used_total=sum(c["used"] for c in code_cards),
        left_total=sum(c["left"] for c in code_cards),
        invited_by=invited_by,
    )
