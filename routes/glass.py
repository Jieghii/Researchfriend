"""排行榜模块：旧财富排名（券商，买方打分）+ 铁牛奖排名（买方机构，卖方打分）。

规则：
- 两个榜单共用机构 / 团队 / 评分 / 评价四张表，用 kind 区分（brokerage / buyside）
- 旧财富排名：维度 研究能力 / 服务能力 / 钞能力，只有买方用户可以打分与评价
- 铁牛奖排名：维度 投资能力 / 知恩图报 / 亲和力，只有卖方用户可以打分与评价
- 评分区间 1-5 星，对应评级：夯 / 很夯 / 非常夯 / 超级夯 / 夯爆了
- 评价匿名展示，其他用户可点赞 / 点踩
- 机构得分 = 其下所有已评分团队得分的平均值，用户不能直接给机构打分
"""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from extensions import db
from models import Brokerage, ResearchTeam, Review, ReviewVote, TeamRating, User
from routes.auth import current_user
from services import (
    BOARD_KINDS,
    now_utc,
    relative_time,
    star_label,
)

bp = Blueprint("glass", __name__)


def _cfg(key):
    return BOARD_KINDS.get(key) or BOARD_KINDS["wealth"]


def dim_keys(kind):
    return [d for d, _ in _cfg("ironbull" if kind == "buyside" else "wealth")["dims"]]


def dim_labels(kind):
    return _cfg("ironbull" if kind == "buyside" else "wealth")["dims"]


def team_score(team):
    """团队得分。返回 {overall, count, vals:{dim_key: 均值}}，无人打分返回 None。"""
    if not team:
        return None
    keys = dim_keys(team.kind)
    rows = TeamRating.query.filter_by(team_id=team.id).all()
    if not rows:
        return None
    vals = {}
    for k in keys:
        nums = [getattr(r, k) for r in rows if getattr(r, k)]
        if not nums:
            return None
        vals[k] = round(sum(nums) / len(nums), 2)
    return {
        "overall": round(sum(vals.values()) / len(vals), 2),
        "count": len(rows),
        "vals": vals,
    }


def team_score_by_id(team_id):
    return team_score(ResearchTeam.query.get(team_id))


def org_score(org):
    """机构得分 = 其下团队得分的平均。"""
    if not org:
        return None
    keys = dim_keys(org.kind)
    teams = ResearchTeam.query.filter_by(brokerage_id=org.id).all()
    acc = {k: [] for k in keys}
    overalls = []
    for t in teams:
        s = team_score(t)
        if s:
            for k in keys:
                acc[k].append(s["vals"][k])
            overalls.append(s["overall"])
    if not overalls:
        return None
    vals = {k: round(sum(v) / len(v), 2) for k, v in acc.items() if v}
    return {
        "overall": round(sum(overalls) / len(overalls), 2),
        "vals": vals,
        "teams": len(teams),
        "rated": len(overalls),
    }


def _review_view(review, viewer_id):
    my_vote = 0
    if viewer_id:
        v = ReviewVote.query.filter_by(review_id=review.id, user_id=viewer_id).first()
        my_vote = v.value if v else 0
    return {
        "id": review.id,
        "content": review.content,
        "created_at": relative_time(review.created_at),
        "ups": review.ups,
        "downs": review.downs,
        "my_vote": my_vote,
        "is_mine": viewer_id == review.author_id,
    }


def _reviews_for(target_type, target_id, viewer_id):
    rows = (
        Review.query.filter_by(target_type=target_type, target_id=target_id)
        .order_by(Review.created_at.desc())
        .all()
    )
    return [_review_view(r, viewer_id) for r in rows]


def _board_view(key, me):
    """构建榜单首页需要的数据。"""
    cfg = _cfg(key)
    kind = cfg["kind"]
    orgs = Brokerage.query.filter_by(kind=kind).order_by(Brokerage.id).all()
    teams = ResearchTeam.query.filter_by(kind=kind).all()

    o_list = []
    for o in orgs:
        s = org_score(o)
        if s:
            o_list.append({"org": o, "score": s})
    o_list.sort(key=lambda x: -x["score"]["overall"])

    t_list = []
    for t in teams:
        s = team_score(t)
        if s:
            t_list.append({"team": t, "org": Brokerage.query.get(t.brokerage_id), "score": s})
    t_list.sort(key=lambda x: -x["score"]["overall"])

    cards = []
    for o in orgs:
        cards.append(
            {
                "org": o,
                "score": org_score(o),
                "teams_n": ResearchTeam.query.filter_by(brokerage_id=o.id).count(),
            }
        )
    return {
        "cfg": cfg,
        "key": key,
        "orgs": orgs,
        "top_orgs": o_list[:3],
        "top_teams": t_list[:3],
        "cards": cards,
        "can_rate": bool(me and me.role == cfg["rater_role"]),
        "me": me,
    }


def _render_board(key):
    me = current_user()
    view = _board_view(key, me)
    return render_template(
        "board.html",
        nav="discover",
        star_labels={1: "夯", 2: "很夯", 3: "非常夯", 4: "超级夯", 5: "夯爆了"},
        **view,
    )


# ---------- 榜单入口 ----------
@bp.route("/glass")
def index():
    """旧财富排名（原玻璃球点评）。"""
    return _render_board("wealth")


@bp.route("/ironbull")
def ironbull():
    """铁牛奖排名。"""
    return _render_board("ironbull")


# ---------- 总榜 ----------
@bp.route("/board/<key>/rank/<kind>")
def rank(key, kind):
    me = current_user()
    cfg = _cfg(key)
    kind_filter = cfg["kind"]
    if kind == "org":
        rows = []
        for o in Brokerage.query.filter_by(kind=kind_filter).order_by(Brokerage.id).all():
            s = org_score(o)
            if s:
                rows.append(
                    {
                        "name": o.name,
                        "score": s,
                        "href": url_for("glass.org_detail", key=key, org_id=o.id),
                        "sub": f"{s['rated']}/{s['teams']} 个团队已评分",
                    }
                )
        title = f"{cfg['org_label']}总榜"
    else:
        rows = []
        for t in ResearchTeam.query.filter_by(kind=kind_filter).all():
            s = team_score(t)
            if s:
                o = Brokerage.query.get(t.brokerage_id)
                rows.append(
                    {
                        "name": t.name,
                        "score": s,
                        "href": url_for("glass.team_detail", key=key, team_id=t.id),
                        "sub": o.name if o else "",
                    }
                )
        title = f"{cfg['team_label']}总榜"
    rows.sort(key=lambda x: -x["score"]["overall"])
    return render_template(
        "board_rank.html",
        nav="discover",
        cfg=cfg,
        key=key,
        title=title,
        rows=rows,
        kind=kind,
    )


# ---------- 机构详情 ----------
@bp.route("/board/<key>/org/<int:org_id>")
def org_detail(key, org_id):
    me = current_user()
    cfg = _cfg(key)
    o = Brokerage.query.get_or_404(org_id)
    score = org_score(o)
    teams = ResearchTeam.query.filter_by(brokerage_id=o.id).order_by(ResearchTeam.id).all()
    team_views = [{"team": t, "score": team_score(t)} for t in teams]
    reviews = _reviews_for("brokerage", o.id, me.id if me else 0)
    return render_template(
        "board_org.html",
        nav="discover",
        cfg=cfg,
        key=key,
        org=o,
        score=score,
        teams=team_views,
        reviews=reviews,
        can_rate=bool(me and me.role == cfg["rater_role"]),
    )


# ---------- 团队详情 ----------
@bp.route("/board/<key>/team/<int:team_id>")
def team_detail(key, team_id):
    me = current_user()
    cfg = _cfg(key)
    t = ResearchTeam.query.get_or_404(team_id)
    o = Brokerage.query.get(t.brokerage_id)
    score = team_score(t)
    mine = TeamRating.query.filter_by(team_id=t.id, user_id=me.id).first() if me else None
    reviews = _reviews_for("team", t.id, me.id if me else 0)
    return render_template(
        "board_team.html",
        nav="discover",
        cfg=cfg,
        key=key,
        team=t,
        org=o,
        score=score,
        mine=mine,
        reviews=reviews,
        can_rate=bool(me and me.role == cfg["rater_role"]),
        star_labels={1: "夯", 2: "很夯", 3: "非常夯", 4: "超级夯", 5: "夯爆了"},
    )


# ---------- 打分 ----------
@bp.route("/api/board/<key>/team/<int:team_id>/rate", methods=["POST"])
def rate_team(key, team_id):
    me = current_user()
    cfg = _cfg(key)
    t = ResearchTeam.query.get_or_404(team_id)
    if me.role != cfg["rater_role"]:
        return jsonify({"ok": False, "error": f"仅{cfg['rater_label']}用户可以评分"}), 403
    data = request.get_json(force=True, silent=True) or {}
    vals = {}
    for k, _label in cfg["dims"]:
        try:
            v = int(data.get(k) or 0)
        except (TypeError, ValueError):
            v = 0
        if v < 1 or v > 5:
            return jsonify({"ok": False, "error": "每个维度都要打 1-5 星"}), 400
        vals[k] = v
    rec = TeamRating.query.filter_by(team_id=t.id, user_id=me.id).first()
    if not rec:
        rec = TeamRating(team_id=t.id, user_id=me.id)
        db.session.add(rec)
    set_rating_dims(rec, vals)
    db.session.commit()
    return jsonify({"ok": True, "score": team_score(t)})


ALL_DIMS = ("research", "service", "capital", "invest", "gratitude", "affinity")


def set_rating_dims(rec, vals):
    """写入本榜单三维，其余维度填 0（兼容旧库里 research/service/capital 的 NOT NULL 约束）。"""
    for k in ALL_DIMS:
        if k not in vals:
            setattr(rec, k, 0)
    for k, v in vals.items():
        setattr(rec, k, v)


# ---------- 新增机构 + 团队并打分 ----------
@bp.route("/api/board/<key>/team/create", methods=["POST"])
def create_team(key):
    """用户自荐新增团队：填写机构名 + 团队名 + 三维评分。

    - 机构按名称查重（限定本榜单 kind）；不存在则自动创建
    - 同机构下同名的团队视为同一团队，复用并覆盖本用户评分
    """
    me = current_user()
    cfg = _cfg(key)
    if me.role != cfg["rater_role"]:
        return jsonify({"ok": False, "error": f"仅{cfg['rater_label']}用户可以新增并打分"}), 403
    data = request.get_json(force=True, silent=True) or {}
    org_name = (data.get("org_name") or data.get("brokerage_name") or "").strip()
    team_name = (data.get("team_name") or "").strip()
    if not org_name or not team_name:
        return jsonify({"ok": False, "error": f"请填写{cfg['org_label']}名称和团队名称"}), 400
    if len(org_name) > 32 or len(team_name) > 32:
        return jsonify({"ok": False, "error": "名称不能超过 32 字"}), 400
    vals = {}
    for k, _label in cfg["dims"]:
        try:
            v = int(data.get(k) or 0)
        except (TypeError, ValueError):
            v = 0
        if v < 1 or v > 5:
            return jsonify({"ok": False, "error": "每个维度都要打 1-5 星"}), 400
        vals[k] = v

    o = Brokerage.query.filter_by(name=org_name, kind=cfg["kind"]).first()
    if not o:
        o = Brokerage(
            name=org_name,
            short_name=org_name[:2],
            intro=f"由用户贡献的虚拟{cfg['org_label']}",
            hue=sum(ord(c) for c in org_name) % 360,
            kind=cfg["kind"],
        )
        db.session.add(o)
        db.session.flush()
    team = ResearchTeam.query.filter_by(brokerage_id=o.id, name=team_name).first()
    if not team:
        team = ResearchTeam(
            brokerage_id=o.id,
            name=team_name,
            intro="由用户贡献的虚拟团队",
            kind=cfg["kind"],
        )
        db.session.add(team)
        db.session.flush()
    rec = TeamRating.query.filter_by(team_id=team.id, user_id=me.id).first()
    if not rec:
        rec = TeamRating(team_id=team.id, user_id=me.id)
        db.session.add(rec)
    set_rating_dims(rec, vals)
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "team_id": team.id,
            "org_id": o.id,
            "redirect": url_for("glass.team_detail", key=key, team_id=team.id),
        }
    )


# ---------- 匿名评价 ----------
@bp.route("/api/board/<key>/review", methods=["POST"])
def add_review(key):
    me = current_user()
    cfg = _cfg(key)
    if me.role != cfg["rater_role"]:
        return jsonify({"ok": False, "error": f"仅{cfg['rater_label']}用户可以评价"}), 403
    data = request.get_json(force=True, silent=True) or {}
    target_type = data.get("target_type")
    target_id = int(data.get("target_id") or 0)
    content = (data.get("content") or "").strip()
    if target_type not in ("brokerage", "team") or not target_id:
        return jsonify({"ok": False, "error": "参数不对"}), 400
    if not content:
        return jsonify({"ok": False, "error": "先写点什么再发布"}), 400
    if len(content) > 300:
        return jsonify({"ok": False, "error": "评价最多 300 字"}), 400
    rec = Review(target_type=target_type, target_id=target_id, author_id=me.id, content=content)
    db.session.add(rec)
    db.session.commit()
    return jsonify({"ok": True, "review": _review_view(rec, me.id)})


@bp.route("/api/board/review/<int:review_id>/vote", methods=["POST"])
def vote_review(review_id):
    me = current_user()
    data = request.get_json(force=True, silent=True) or {}
    try:
        value = int(data.get("value") or 0)
    except (TypeError, ValueError):
        value = 0
    if value not in (1, -1):
        return jsonify({"ok": False, "error": "参数不对"}), 400
    rec = ReviewVote.query.filter_by(review_id=review_id, user_id=me.id).first()
    if rec and rec.value == value:
        db.session.delete(rec)
        db.session.commit()
        return jsonify({"ok": True, "my_vote": 0})
    if not rec:
        rec = ReviewVote(review_id=review_id, user_id=me.id)
        db.session.add(rec)
    rec.value = value
    db.session.commit()
    review = Review.query.get(review_id)
    # 评价被点赞：作者 +2 修炼值
    if value == 1 and review:
        author = User.query.get(review.author_id)
        if author:
            try:
                from services import add_exp

                add_exp(author, "like", ref_id=review.id, desc="评价被点赞")
                db.session.commit()
            except Exception:
                db.session.rollback()
    return jsonify({"ok": True, "my_vote": value, "ups": review.ups, "downs": review.downs})


# ---------- 兼容旧链接 ----------
@bp.route("/glass/brokerage/<int:brokerage_id>")
def old_brokerage(brokerage_id):
    return redirect(url_for("glass.org_detail", key="wealth", org_id=brokerage_id))


@bp.route("/glass/team/<int:team_id>")
def old_team(team_id):
    return redirect(url_for("glass.team_detail", key="wealth", team_id=team_id))


@bp.route("/glass/rank/<kind>")
def old_rank(kind):
    return redirect(url_for("glass.rank", key="wealth", kind=kind))
