"""管理后台：独立 /admin 入口 + 管理员密码。可管理用户、反馈，并生成邀请码。"""

from functools import wraps

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import bindparam

from codes import gen_invite_code
from extensions import db
from models import (
    AdminNotice,
    Brokerage,
    Feedback,
    InviteCode,
    ResearchTeam,
    Review,
    ReviewVote,
    Thought,
    ThoughtTag,
    User,
)
from services import relative_time

bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_SESSION_KEY = "admin_ok"


def admin_logged_in():
    return bool(session.get(ADMIN_SESSION_KEY))


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not admin_logged_in():
            return redirect(url_for("admin.login"))
        return fn(*args, **kwargs)

    return wrapper


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        pwd = request.form.get("password") or ""
        if pwd == current_app.config.get("ADMIN_PASSWORD"):
            session[ADMIN_SESSION_KEY] = True
            return redirect(url_for("admin.dashboard"))
        error = "管理员密码不对"
    return render_template("admin/login.html", error=error, logged=admin_logged_in())


@bp.route("/logout")
def logout():
    session.pop(ADMIN_SESSION_KEY, None)
    return redirect(url_for("admin.login"))


@bp.route("/")
@admin_required
def dashboard():
    stats = {
        "users": User.query.count(),
        "buyers": User.query.filter_by(role="buyer").count(),
        "sellers": User.query.filter_by(role="seller").count(),
        "banned": User.query.filter_by(is_banned=True).count(),
        "feedbacks": Feedback.query.count(),
        "open_feedbacks": Feedback.query.filter_by(status="open").count(),
        "invites": InviteCode.query.count(),
        "thoughts": Thought.query.count(),
        "reviews": Review.query.count(),
        "brokerages": Brokerage.query.count(),
        "teams": ResearchTeam.query.count(),
    }
    latest_users = User.query.order_by(User.created_at.desc()).limit(8).all()
    latest_fb = Feedback.query.order_by(Feedback.created_at.desc()).limit(5).all()
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        latest_users=latest_users,
        latest_fb=latest_fb,
        using_default_password=bool(current_app.config.get("ADMIN_IS_DEFAULT")),
    )


@bp.route("/users")
@admin_required
def users():
    q = (request.args.get("q") or "").strip()
    query = User.query
    if q:
        query = query.filter(User.nickname.contains(q))
    rows = query.order_by(User.created_at.desc()).limit(200).all()
    view = []
    for u in rows:
        code = InviteCode.query.filter_by(owner_user_id=u.id).first()
        view.append(
            {
                "user": u,
                "role": "买方" if u.role == "buyer" else ("卖方" if u.role == "seller" else "未设置"),
                "joined": relative_time(u.created_at),
                "code": code.code if code else "—",
                "code_used": code.used_count if code else 0,
                "code_max": code.max_uses if code else 0,
            }
        )
    return render_template("admin/users.html", rows=view, q=q)


@bp.route("/users/<int:user_id>/ban", methods=["POST"])
@admin_required
def toggle_ban(user_id):
    u = User.query.get_or_404(user_id)
    u.is_banned = not u.is_banned
    db.session.commit()
    return jsonify({"ok": True, "banned": u.is_banned})


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    u = User.query.get_or_404(user_id)
    db.session.execute(db.text("DELETE FROM friend_requests WHERE from_user_id=:i OR to_user_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM friendships WHERE user_low_id=:i OR user_high_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM skips WHERE user_id=:i OR skipped_user_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM user_tags WHERE user_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM likes WHERE user_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM comments WHERE author_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM thought_tags WHERE thought_id IN (SELECT id FROM thoughts WHERE author_id=:i)"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM comments WHERE thought_id IN (SELECT id FROM thoughts WHERE author_id=:i)"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM likes WHERE thought_id IN (SELECT id FROM thoughts WHERE author_id=:i)"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM thoughts WHERE author_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM messages WHERE sender_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_a_id=:i OR user_b_id=:i)"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM conversations WHERE user_a_id=:i OR user_b_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM review_votes WHERE user_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM reviews WHERE author_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM team_ratings WHERE user_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM feedbacks WHERE user_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM password_reset_tokens WHERE user_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM invite_codes WHERE owner_user_id=:i"), {"i": user_id})
    db.session.execute(db.text("DELETE FROM users WHERE id=:i"), {"i": user_id})
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/feedbacks")
@admin_required
def feedbacks():
    status = request.args.get("status") or "all"
    query = Feedback.query
    if status in ("open", "resolved"):
        query = query.filter_by(status=status)
    rows = query.order_by(Feedback.created_at.desc()).limit(200).all()
    view = []
    for f in rows:
        u = User.query.get(f.user_id)
        view.append(
            {
                "id": f.id,
                "nickname": u.nickname if u else "已注销",
                "content": f.content,
                "contact": f.contact,
                "status": f.status,
                "admin_note": f.admin_note,
                "time": relative_time(f.created_at),
                "at": f.created_at.strftime("%Y-%m-%d %H:%M"),
            }
        )
    return render_template("admin/feedbacks.html", rows=view, status=status)


@bp.route("/feedbacks/<int:fid>/resolve", methods=["POST"])
@admin_required
def resolve_feedback(fid):
    f = Feedback.query.get_or_404(fid)
    data = request.get_json(force=True, silent=True) or {}
    f.status = data.get("status") or "resolved"
    f.admin_note = (data.get("note") or "")[:300]
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/invites")
@admin_required
def invites():
    rows = InviteCode.query.order_by(InviteCode.created_at.desc()).limit(200).all()
    view = []
    for c in rows:
        owner = User.query.get(c.owner_user_id) if c.owner_user_id else None
        invited = c.invited_users
        view.append(
            {
                "id": c.id,
                "code": c.code,
                "owner": owner.nickname if owner else "系统生成",
                "max_uses": c.max_uses,
                "used": len(invited),
                "active": c.is_active,
                "invited": [u.nickname for u in invited],
                "created": c.created_at.strftime("%Y-%m-%d %H:%M"),
            }
        )
    return render_template("admin/invites.html", rows=view)


@bp.route("/invites/create", methods=["POST"])
@admin_required
def create_invite():
    data = request.get_json(force=True, silent=True) or {}
    try:
        count = int(data.get("count") or 1)
    except (TypeError, ValueError):
        count = 1
    count = max(1, min(count, 50))
    try:
        max_uses = int(data.get("max_uses") or 5)
    except (TypeError, ValueError):
        max_uses = 5
    max_uses = max(1, min(max_uses, 999))
    note = (data.get("note") or "")[:64]

    created = []
    for _ in range(count):
        code = InviteCode(
            code=gen_invite_code(exists=lambda c: InviteCode.query.filter_by(code=c).first()),
            owner_user_id=None,
            max_uses=max_uses,
            note=note,
        )
        db.session.add(code)
        db.session.flush()
        created.append(code.code)
    db.session.commit()
    return jsonify({"ok": True, "codes": created})


@bp.route("/invites/<int:cid>/toggle", methods=["POST"])
@admin_required
def toggle_invite(cid):
    c = InviteCode.query.get_or_404(cid)
    c.is_active = not c.is_active
    db.session.commit()
    return jsonify({"ok": True, "active": c.is_active})


# ---------- 内容管理（删除随想 / 评价，附带理由通知用户） ----------
@bp.route("/content")
@admin_required
def content():
    thoughts = (
        Thought.query.order_by(Thought.created_at.desc())
        .limit(100)
        .all()
    )
    reviews = (
        Review.query.order_by(Review.created_at.desc())
        .limit(100)
        .all()
    )
    t_users = {u.id: u for u in User.query.filter(User.id.in_({t.author_id for t in thoughts} or {0})).all()}
    r_users = {u.id: u for u in User.query.filter(User.id.in_({r.author_id for r in reviews} or {0})).all()}
    org_map = {o.id: o for o in Brokerage.query.all()}
    team_map = {t.id: t for t in ResearchTeam.query.all()}

    t_view = []
    for t in thoughts:
        u = t_users.get(t.author_id)
        t_view.append(
            {
                "id": t.id,
                "nickname": u.nickname if u else "已注销",
                "body": (t.body or "")[:120],
                "time": relative_time(t.created_at),
            }
        )
    r_view = []
    for r in reviews:
        u = r_users.get(r.author_id)
        if r.target_type == "brokerage":
            label = org_map.get(r.target_id)
            label = f"机构「{label.name}」" if label else "机构"
        else:
            label = team_map.get(r.target_id)
            label = f"团队「{label.name}」" if label else "团队"
        r_view.append(
            {
                "id": r.id,
                "nickname": u.nickname if u else "已注销",
                "target": label,
                "content": (r.content or "")[:120],
                "time": relative_time(r.created_at),
            }
        )
    return render_template("admin/content.html", thoughts=t_view, reviews=r_view)


# ---------- 机构与团队管理（改名） ----------
@bp.route("/orgs")
@admin_required
def orgs():
    groups = []
    for kind, label in (("brokerage", "券商"), ("buyside", "买方机构")):
        rows = Brokerage.query.filter_by(kind=kind).order_by(Brokerage.id).all()
        items = []
        for o in rows:
            teams = ResearchTeam.query.filter_by(brokerage_id=o.id).order_by(ResearchTeam.id).all()
            items.append({"org": o, "teams": teams})
        groups.append({"kind": kind, "label": label, "items": items})
    return render_template("admin/orgs.html", groups=groups)


@bp.route("/api/orgs/<int:oid>/rename", methods=["POST"])
@admin_required
def rename_org(oid):
    o = Brokerage.query.get_or_404(oid)
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "名称不能为空"}), 400
    if len(name) > 32:
        return jsonify({"ok": False, "error": "名称不能超过 32 字"}), 400
    dup = Brokerage.query.filter(Brokerage.name == name, Brokerage.id != o.id).first()
    if dup:
        return jsonify({"ok": False, "error": "已存在同名机构"}), 400
    o.name = name
    o.short_name = name[:2]
    db.session.commit()
    return jsonify({"ok": True, "name": o.name})


@bp.route("/api/orgs/<int:oid>/update", methods=["POST"])
@admin_required
def update_org(oid):
    o = Brokerage.query.get_or_404(oid)
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    intro = (data.get("intro") or "").strip()
    if name:
        if len(name) > 32:
            return jsonify({"ok": False, "error": "名称不能超过 32 字"}), 400
        dup = Brokerage.query.filter(Brokerage.name == name, Brokerage.id != o.id).first()
        if dup:
            return jsonify({"ok": False, "error": "已存在同名机构"}), 400
        o.name = name
        o.short_name = name[:2]
    if len(intro) > 200:
        return jsonify({"ok": False, "error": "简介不能超过 200 字"}), 400
    o.intro = intro or None
    db.session.commit()
    return jsonify({"ok": True, "name": o.name, "intro": o.intro})


@bp.route("/api/orgs/<int:oid>/delete", methods=["POST"])
@admin_required
def delete_org(oid):
    """删除机构：先级联删下属团队（含其评分与评价），再清掉对机构的评价，最后删机构本身。"""
    o = Brokerage.query.get_or_404(oid)
    team_ids = [t.id for t in ResearchTeam.query.filter_by(brokerage_id=oid).all()]
    if team_ids:
        db.session.execute(
            db.text("DELETE FROM team_ratings WHERE team_id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            ),
            {"ids": team_ids},
        )
        db.session.execute(
            db.text("DELETE FROM reviews WHERE target_type='team' AND target_id IN :ids").bindparams(
                bindparam("ids", expanding=True)
            ),
            {"ids": team_ids},
        )
        ResearchTeam.query.filter_by(brokerage_id=oid).delete()
    db.session.execute(
        db.text("DELETE FROM reviews WHERE target_type='brokerage' AND target_id=:oid"),
        {"oid": oid},
    )
    db.session.delete(o)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/teams/<int:tid>/rename", methods=["POST"])
@admin_required
def rename_team(tid):
    t = ResearchTeam.query.get_or_404(tid)
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "名称不能为空"}), 400
    if len(name) > 32:
        return jsonify({"ok": False, "error": "名称不能超过 32 字"}), 400
    t.name = name
    db.session.commit()
    return jsonify({"ok": True, "name": t.name})


@bp.route("/api/teams/<int:tid>/update", methods=["POST"])
@admin_required
def update_team(tid):
    t = ResearchTeam.query.get_or_404(tid)
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    intro = (data.get("intro") or "").strip()
    if name:
        if len(name) > 32:
            return jsonify({"ok": False, "error": "名称不能超过 32 字"}), 400
        t.name = name
    if len(intro) > 200:
        return jsonify({"ok": False, "error": "简介不能超过 200 字"}), 400
    t.intro = intro or None
    db.session.commit()
    return jsonify({"ok": True, "name": t.name, "intro": t.intro})


@bp.route("/api/teams/<int:tid>/delete", methods=["POST"])
@admin_required
def delete_team(tid):
    """删除团队：先删其评分与评价，再删团队。"""
    t = ResearchTeam.query.get_or_404(tid)
    db.session.execute(
        db.text("DELETE FROM team_ratings WHERE team_id=:tid"), {"tid": tid}
    )
    db.session.execute(
        db.text("DELETE FROM reviews WHERE target_type='team' AND target_id=:tid"),
        {"tid": tid},
    )
    db.session.delete(t)
    db.session.commit()
    return jsonify({"ok": True})


# ---------- 删除随想 / 评价（附带理由通知用户） ----------
@bp.route("/api/thoughts/<int:tid>/delete", methods=["POST"])
@admin_required
def delete_thought(tid):
    th = Thought.query.get_or_404(tid)
    data = request.get_json(force=True, silent=True) or {}
    reason = (data.get("reason") or "").strip()[:300]
    snippet = (th.body or "")[:100]
    author_id = th.author_id
    db.session.add(
        AdminNotice(
            user_id=author_id,
            kind="thought_deleted",
            title="你的一条随想已被管理员删除",
            reason=reason,
            snippet=snippet,
        )
    )
    from models import Comment, Like

    Like.query.filter_by(thought_id=tid).delete()
    Comment.query.filter_by(thought_id=tid).delete()
    ThoughtTag.query.filter_by(thought_id=tid).delete()
    db.session.delete(th)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/reviews/<int:rid>/delete", methods=["POST"])
@admin_required
def delete_review(rid):
    r = Review.query.get_or_404(rid)
    data = request.get_json(force=True, silent=True) or {}
    reason = (data.get("reason") or "").strip()[:300]
    target_label = "机构" if r.target_type == "brokerage" else "团队"
    db.session.add(
        AdminNotice(
            user_id=r.author_id,
            kind="review_deleted",
            title=f"你对{target_label}的一条评价已被管理员删除",
            reason=reason,
            snippet=(r.content or "")[:100],
        )
    )
    ReviewVote.query.filter_by(review_id=rid).delete()
    db.session.delete(r)
    db.session.commit()
    return jsonify({"ok": True})
