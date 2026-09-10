"""发现页：随想、旧财富排名、铁牛奖排名。"""

from flask import Blueprint, render_template, url_for

from models import Brokerage, ResearchTeam, Thought
from routes.auth import current_user
from services import friend_ids

bp = Blueprint("discover", __name__)


def _stat_counts(me):
    from models import Feedback, InviteCode

    friends_n = len(friend_ids(me.id))
    my_code = InviteCode.query.filter_by(owner_user_id=me.id).first()
    invite_left = 0
    if my_code:
        invite_left = max(0, my_code.max_uses - my_code.used_count)
    return {
        "friends_n": friends_n,
        "wealth_orgs_n": Brokerage.query.filter_by(kind="brokerage").count(),
        "wealth_teams_n": ResearchTeam.query.filter_by(kind="brokerage").count(),
        "iron_orgs_n": Brokerage.query.filter_by(kind="buyside").count(),
        "iron_teams_n": ResearchTeam.query.filter_by(kind="buyside").count(),
        "invite_left": invite_left,
        "feedback_n": Feedback.query.filter_by(user_id=me.id).count(),
        "thoughts_n": Thought.query.filter_by(author_id=me.id).count(),
    }


@bp.route("/discover")
def page():
    me = current_user()
    stats = _stat_counts(me)
    entries = [
        {
            "key": "thoughts",
            "title": "随想",
            "desc": "发短内容、看看同行在聊什么",
            "href": url_for("thoughts.timeline"),
            "icon": "pen",
            "extra": f"我发过 {stats['thoughts_n']} 条" if stats["thoughts_n"] else "",
        },
        {
            "key": "wealth",
            "title": "旧财富排名",
            "desc": "券商与研究团队排行榜，由买方研友打分与匿名评价",
            "href": url_for("glass.index"),
            "icon": "glass",
            "extra": f"{stats['wealth_orgs_n']} 家券商 · {stats['wealth_teams_n']} 个团队",
        },
        {
            "key": "ironbull",
            "title": "铁牛奖排名",
            "desc": "买方机构与买方团队排行榜，由卖方研友打分与匿名评价",
            "href": url_for("glass.ironbull"),
            "icon": "bull",
            "extra": f"{stats['iron_orgs_n']} 家买方 · {stats['iron_teams_n']} 个团队",
        },
    ]
    return render_template("discover.html", nav="discover", entries=entries, stats=stats)
