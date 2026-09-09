"""玻璃球点评：券商 / 研究团队排行榜、评分与匿名评价。

规则：
- 评分区间 1-5 星，三个维度：研究能力、服务能力、钞能力
- 只有买方用户可以打分与评价；卖方点击会收到「仅买方用户可以评价」提示
- 评价匿名展示，其他用户可点赞 / 点踩
- 券商得分 = 其下所有已评分团队得分的平均值，用户不能直接给券商打分
"""

from flask import Blueprint, jsonify, render_template, request, url_for

from extensions import db
from models import Brokerage, ResearchTeam, Review, ReviewVote, TeamRating, User
from routes.auth import current_user
from services import now_utc, relative_time

bp = Blueprint("glass", __name__)

DIMENSIONS = [
    ("research", "研究能力"),
    ("service", "服务能力"),
    ("capital", "钞能力"),
]


def team_score(team_id):
    rows = TeamRating.query.filter_by(team_id=team_id).all()
    if not rows:
        return None
    n = len(rows)
    research = sum(r.research for r in rows) / n
    service = sum(r.service for r in rows) / n
    capital = sum(r.capital for r in rows) / n
    return {
        "research": round(research, 2),
        "service": round(service, 2),
        "capital": round(capital, 2),
        "overall": round((research + service + capital) / 3, 2),
        "count": n,
    }


def brokerage_score(brokerage_id):
    teams = ResearchTeam.query.filter_by(brokerage_id=brokerage_id).all()
    acc = {"research": [], "service": [], "capital": [], "overall": []}
    for t in teams:
        s = team_score(t.id)
        if s:
            for k in acc:
                acc[k].append(s[k])
    if not acc["overall"]:
        return None
    return {
        "research": round(sum(acc["research"]) / len(acc["research"]), 2),
        "service": round(sum(acc["service"]) / len(acc["service"]), 2),
        "capital": round(sum(acc["capital"]) / len(acc["capital"]), 2),
        "overall": round(sum(acc["overall"]) / len(acc["overall"]), 2),
        "teams": len(teams),
        "rated": len(acc["overall"]),
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


@bp.route("/glass")
def index():
    brokerages = Brokerage.query.order_by(Brokerage.id).all()
    teams = ResearchTeam.query.all()

    b_list = []
    for b in brokerages:
        s = brokerage_score(b.id)
        if s:
            b_list.append({"brokerage": b, "score": s})
    b_list.sort(key=lambda x: -x["score"]["overall"])

    t_list = []
    for t in teams:
        s = team_score(t.id)
        if s:
            t_list.append({"team": t, "brokerage": Brokerage.query.get(t.brokerage_id), "score": s})
    t_list.sort(key=lambda x: -x["score"]["overall"])

    cards = []
    for b in brokerages:
        cards.append({"brokerage": b, "score": brokerage_score(b.id),
                      "teams_n": ResearchTeam.query.filter_by(brokerage_id=b.id).count()})

    return render_template(
        "glass.html",
        nav="discover",
        top_brokerages=b_list[:3],
        top_teams=t_list[:3],
        cards=cards,
        brokerages=brokerages,
        dimensions=DIMENSIONS,
    )


@bp.route("/glass/rank/<kind>")
def rank(kind):
    if kind == "brokerage":
        rows = []
        for b in Brokerage.query.order_by(Brokerage.id).all():
            s = brokerage_score(b.id)
            if s:
                rows.append({
                    "name": b.name, "score": s,
                    "href": url_for("glass.brokerage_detail", brokerage_id=b.id),
                    "sub": f"{s['rated']}/{s['teams']} 个团队已评分",
                })
        title = "券商总榜"
    else:
        rows = []
        for t in ResearchTeam.query.all():
            s = team_score(t.id)
            if s:
                b = Brokerage.query.get(t.brokerage_id)
                rows.append({
                    "name": t.name, "score": s,
                    "href": url_for("glass.team_detail", team_id=t.id),
                    "sub": b.name if b else "",
                })
        title = "团队总榜"
    rows.sort(key=lambda x: -x["score"]["overall"])
    return render_template("glass_rank.html", nav="discover", title=title, rows=rows,
                           kind=kind, dimensions=DIMENSIONS)


@bp.route("/glass/brokerage/<int:brokerage_id>")
def brokerage_detail(brokerage_id):
    me = current_user()
    b = Brokerage.query.get_or_404(brokerage_id)
    score = brokerage_score(b.id)
    teams = ResearchTeam.query.filter_by(brokerage_id=b.id).order_by(ResearchTeam.id).all()
    team_views = [{"team": t, "score": team_score(t.id)} for t in teams]
    reviews = _reviews_for("brokerage", b.id, me.id)
    return render_template(
        "glass_brokerage.html",
        nav="discover",
        brokerage=b,
        score=score,
        teams=team_views,
        reviews=reviews,
        dimensions=DIMENSIONS,
    )


@bp.route("/glass/team/<int:team_id>")
def team_detail(team_id):
    me = current_user()
    t = ResearchTeam.query.get_or_404(team_id)
    b = Brokerage.query.get(t.brokerage_id)
    score = team_score(t.id)
    mine = TeamRating.query.filter_by(team_id=t.id, user_id=me.id).first()
    reviews = _reviews_for("team", t.id, me.id)
    return render_template(
        "glass_team.html",
        nav="discover",
        team=t,
        brokerage=b,
        score=score,
        mine=mine,
        reviews=reviews,
        dimensions=DIMENSIONS,
    )


@bp.route("/api/glass/team/<int:team_id>/rate", methods=["POST"])
def rate_team(team_id):
    me = current_user()
    data = request.get_json(force=True, silent=True) or {}
    if me.role != "buyer":
        return jsonify({"ok": False, "error": "仅买方用户可以评分"}), 403
    vals = {}
    for key, _label in DIMENSIONS:
        try:
            v = int(data.get(key) or 0)
        except (TypeError, ValueError):
            v = 0
        if v < 1 or v > 5:
            return jsonify({"ok": False, "error": "评分需要在 1-5 星之间"}), 400
        vals[key] = v
    rec = TeamRating.query.filter_by(team_id=team_id, user_id=me.id).first()
    if not rec:
        rec = TeamRating(team_id=team_id, user_id=me.id)
        db.session.add(rec)
    rec.research = vals["research"]
    rec.service = vals["service"]
    rec.capital = vals["capital"]
    db.session.commit()
    return jsonify({"ok": True, "score": team_score(team_id)})


@bp.route("/api/glass/team/create", methods=["POST"])
def create_team():
    """买方用户自荐新增团队：填写券商名 + 团队名 + 三维评分。

    - 券商按名称查重；不存在则自动创建（hue 由名称 hash 得到，简介为占位文案）
    - 同券商下同名的团队视为同一团队，复用并更新本用户的评分
    - 创建/更新成功后跳转团队详情页
    """
    me = current_user()
    if me.role != "buyer":
        return jsonify({"ok": False, "error": "仅买方用户可以新增团队评分"}), 403
    data = request.get_json(force=True, silent=True) or {}
    brokerage_name = (data.get("brokerage_name") or "").strip()
    team_name = (data.get("team_name") or "").strip()
    if not brokerage_name or not team_name:
        return jsonify({"ok": False, "error": "请填写券商名称和团队名称"}), 400
    if len(brokerage_name) > 32 or len(team_name) > 32:
        return jsonify({"ok": False, "error": "名称不能超过 32 字"}), 400
    vals = {}
    for key, _label in DIMENSIONS:
        try:
            v = int(data.get(key) or 0)
        except (TypeError, ValueError):
            v = 0
        if v < 1 or v > 5:
            return jsonify({"ok": False, "error": "每个维度都要打 1-5 星"}), 400
        vals[key] = v
    b = Brokerage.query.filter_by(name=brokerage_name).first()
    if not b:
        hue = sum(ord(c) for c in brokerage_name) % 360
        b = Brokerage(
            name=brokerage_name,
            short_name=brokerage_name[:2],
            intro="由用户贡献的虚拟券商",
            hue=hue,
        )
        db.session.add(b)
        db.session.flush()
    team = ResearchTeam.query.filter_by(brokerage_id=b.id, name=team_name).first()
    if not team:
        team = ResearchTeam(
            brokerage_id=b.id,
            name=team_name,
            intro="由用户贡献的虚拟团队",
        )
        db.session.add(team)
        db.session.flush()
    rec = TeamRating.query.filter_by(team_id=team.id, user_id=me.id).first()
    if rec:
        rec.research = vals["research"]
        rec.service = vals["service"]
        rec.capital = vals["capital"]
    else:
        db.session.add(TeamRating(
            team_id=team.id,
            user_id=me.id,
            research=vals["research"],
            service=vals["service"],
            capital=vals["capital"],
        ))
    db.session.commit()
    return jsonify({
        "ok": True,
        "team_id": team.id,
        "brokerage_id": b.id,
        "redirect": url_for("glass.team_detail", team_id=team.id),
    })


@bp.route("/api/glass/review", methods=["POST"])
def add_review():
    me = current_user()
    data = request.get_json(force=True, silent=True) or {}
    if me.role != "buyer":
        return jsonify({"ok": False, "error": "仅买方用户可以评价"}), 403
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


@bp.route("/api/glass/review/<int:review_id>/vote", methods=["POST"])
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
        db.session.delete(rec)  # 再点一次 = 取消
        db.session.commit()
        return jsonify({"ok": True, "my_vote": 0})
    if not rec:
        rec = ReviewVote(review_id=review_id, user_id=me.id)
        db.session.add(rec)
    rec.value = value
    db.session.commit()
    review = Review.query.get(review_id)
    return jsonify({"ok": True, "my_vote": value, "ups": review.ups, "downs": review.downs})
