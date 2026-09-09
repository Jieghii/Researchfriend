"""邀请码页面：我的邀请码、额度与使用情况、我是被谁邀请的。"""

from flask import Blueprint, jsonify, render_template, request

from extensions import db
from models import InviteCode, User
from routes.auth import current_user

bp = Blueprint("invite", __name__)


def ensure_my_code(user):
    """确保用户有自己的邀请码（老账号补一张）。"""
    code = InviteCode.query.filter_by(owner_user_id=user.id).first()
    if code:
        return code
    from codes import gen_invite_code

    code = InviteCode(
        code=gen_invite_code(exists=lambda c: InviteCode.query.filter_by(code=c).first()),
        owner_user_id=user.id,
        max_uses=5,
    )
    db.session.add(code)
    db.session.commit()
    return code


@bp.route("/invite")
def page():
    me = current_user()
    my_code = ensure_my_code(me)

    invited_by = None
    if me.invite_code_id:
        used = InviteCode.query.get(me.invite_code_id)
        if used:
            owner = User.query.get(used.owner_user_id) if used.owner_user_id else None
            invited_by = {
                "code": used.code,
                "owner": owner.nickname if owner else "官方邀请码",
            }

    invited_users = my_code.invited_users
    slots = []
    for i in range(my_code.max_uses):
        if i < len(invited_users):
            u = invited_users[i]
            slots.append({"used": True, "nickname": u.nickname, "at": u.created_at})
        else:
            slots.append({"used": False, "nickname": None, "at": None})

    return render_template(
        "invite.html",
        nav="discover",
        my_code=my_code,
        slots=slots,
        used=len(invited_users),
        left=max(0, my_code.max_uses - len(invited_users)),
        invited_by=invited_by,
    )
