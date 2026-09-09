"""发现页：通讯录、玻璃球点评、用户反馈、邀请码、随想。"""

from flask import Blueprint, render_template, url_for

from models import Brokerage, Feedback, Friendship, InviteCode, ResearchTeam, User
from routes.auth import current_user
from services import friend_ids

bp = Blueprint("discover", __name__)


def _stat_counts(me):
    low, high = (me.id, 0)
    friends_n = len(friend_ids(me.id))
    my_code = InviteCode.query.filter_by(owner_user_id=me.id).first()
    invite_left = 0
    if my_code:
        invite_left = max(0, my_code.max_uses - my_code.used_count)
    feedback_n = Feedback.query.filter_by(user_id=me.id).count()
    thoughts_n = 0
    from extensions import db
    from models import Thought
    thoughts_n = Thought.query.filter_by(author_id=me.id).count()
    return {
        "friends_n": friends_n,
        "brokerages_n": Brokerage.query.count(),
        "teams_n": ResearchTeam.query.count(),
        "invite_left": invite_left,
        "feedback_n": feedback_n,
        "thoughts_n": thoughts_n,
    }


@bp.route("/discover")
def page():
    me = current_user()
    stats = _stat_counts(me)
    entries = [
        {
            "key": "contacts",
            "title": "通讯录",
            "desc": "你的好友都在这儿，点进去随时开聊",
            "href": url_for("profile.friends_page"),
            "icon": "user",
            "extra": f"{stats['friends_n']} 位好友",
        },
        {
            "key": "thoughts",
            "title": "随想",
            "desc": "发短内容、看看同行在聊什么",
            "href": url_for("thoughts.timeline"),
            "icon": "pen",
            "extra": f"我发过 {stats['thoughts_n']} 条" if stats["thoughts_n"] else "",
        },
        {
            "key": "glass",
            "title": "玻璃球点评",
            "desc": "券商与研究团队排行榜，买方匿名评价",
            "href": url_for("glass.index"),
            "icon": "glass",
            "extra": f"{stats['brokerages_n']} 家机构 · {stats['teams_n']} 个团队",
        },
        {
            "key": "feedback",
            "title": "用户反馈",
            "desc": "遇到 bug 或有想法？告诉我们",
            "href": url_for("feedback.page"),
            "icon": "comment",
            "extra": f"已提交 {stats['feedback_n']} 条" if stats["feedback_n"] else "",
        },
        {
            "key": "invite",
            "title": "邀请码",
            "desc": "查看你的邀请码与剩余名额",
            "href": url_for("invite.page"),
            "icon": "gift",
            "extra": f"剩余 {stats['invite_left']} 个名额",
        },
    ]
    return render_template("discover.html", nav="discover", entries=entries, stats=stats)
