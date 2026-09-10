from datetime import datetime

from extensions import db


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(16), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(8))  # buyer / seller
    years = db.Column(db.String(16))
    signature = db.Column(db.String(80))
    last_active_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tags_skipped = db.Column(db.Boolean, default=False)
    # 邮箱（选填，用于找回密码）
    email = db.Column(db.String(120), index=True)
    # 本账号是通过哪张邀请码注册的
    invite_code_id = db.Column(db.Integer, db.ForeignKey("invite_codes.id"))
    # 是否被封禁（管理后台用）
    is_banned = db.Column(db.Boolean, default=False)
    # 修炼值（决定境界与权限）
    exp = db.Column(db.Integer, nullable=False, default=0)
    # 个人资料（身份/年限）上次修改时间：一个月只能改一次
    profile_updated_at = db.Column(db.DateTime)

    @property
    def realm(self):
        from services import realm_of

        return realm_of(self.exp or 0)


class InviteCode(db.Model):
    """邀请码。每位用户有一张自己的码，额度 5 人；管理员可生成系统码。"""

    __tablename__ = "invite_codes"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    max_uses = db.Column(db.Integer, nullable=False, default=5)
    note = db.Column(db.String(64))
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def used_count(self):
        return User.query.filter_by(invite_code_id=self.id).count()

    @property
    def invited_users(self):
        return User.query.filter_by(invite_code_id=self.id).order_by(User.created_at).all()

    @property
    def is_full(self):
        return self.used_count >= self.max_uses


class PasswordResetToken(db.Model):
    """邮箱找回密码的重置令牌。"""

    __tablename__ = "password_reset_tokens"
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Brokerage(db.Model):
    """机构。kind=brokerage 为券商（旧财富排名），kind=buyside 为买方机构（铁牛奖）。
    均为虚构机构，非真实信息。"""

    __tablename__ = "brokerages"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False, index=True)
    short_name = db.Column(db.String(16))
    intro = db.Column(db.String(200))
    hue = db.Column(db.Integer, default=0)  # 头像色块色相
    # brokerage=券商（卖方，旧财富排名）；buyside=买方机构（铁牛奖）
    kind = db.Column(db.String(16), nullable=False, default="brokerage", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ResearchTeam(db.Model):
    """机构下属团队。kind 与所属机构一致。"""

    __tablename__ = "research_teams"
    id = db.Column(db.Integer, primary_key=True)
    brokerage_id = db.Column(db.Integer, db.ForeignKey("brokerages.id"), nullable=False, index=True)
    name = db.Column(db.String(32), nullable=False)
    intro = db.Column(db.String(200))
    kind = db.Column(db.String(16), nullable=False, default="brokerage", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TeamRating(db.Model):
    """团队三维打分。

    - 旧财富排名（kind=brokerage，买方打分）：research 研究能力 / service 服务能力 / capital 钞能力
    - 铁牛奖（kind=buyside，卖方打分）：invest 投资能力 / gratitude 知恩图报 / affinity 亲和力
    """

    __tablename__ = "team_ratings"
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("research_teams.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    research = db.Column(db.Integer)  # 研究能力 1-5（旧财富）
    service = db.Column(db.Integer)  # 服务能力 1-5（旧财富）
    capital = db.Column(db.Integer)  # 钞能力 1-5（旧财富）
    invest = db.Column(db.Integer)  # 投资能力 1-5（铁牛奖）
    gratitude = db.Column(db.Integer)  # 知恩图报 1-5（铁牛奖）
    affinity = db.Column(db.Integer)  # 亲和力 1-5（铁牛奖）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("team_id", "user_id"),)


class Review(db.Model):
    """匿名评价。target_type: brokerage / team。仅买方可发，展示时匿名。"""

    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    target_type = db.Column(db.String(16), nullable=False, index=True)
    target_id = db.Column(db.Integer, nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    content = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @property
    def ups(self):
        return ReviewVote.query.filter_by(review_id=self.id, value=1).count()

    @property
    def downs(self):
        return ReviewVote.query.filter_by(review_id=self.id, value=-1).count()


class ReviewVote(db.Model):
    """对评价的点赞 / 点踩。value: 1 赞 / -1 踩。"""

    __tablename__ = "review_votes"
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("reviews.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    value = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("review_id", "user_id"),)


class Feedback(db.Model):
    """用户反馈。"""

    __tablename__ = "feedbacks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    content = db.Column(db.String(500), nullable=False)
    contact = db.Column(db.String(64))
    status = db.Column(db.String(16), nullable=False, default="open", index=True)  # open / resolved
    admin_note = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Tag(db.Model):
    __tablename__ = "tags"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), unique=True, nullable=False, index=True)
    kind = db.Column(db.String(16), nullable=False)  # industry / stock
    is_preset = db.Column(db.Boolean, default=True)
    last_rank = db.Column(db.Integer)
    current_rank = db.Column(db.Integer)


class UserTag(db.Model):
    __tablename__ = "user_tags"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    tag_id = db.Column(db.Integer, db.ForeignKey("tags.id"), nullable=False, index=True)
    __table_args__ = (db.UniqueConstraint("user_id", "tag_id"),)


class FriendRequest(db.Model):
    """好友请求：状态为单一字段 pending / accepted / rejected。"""

    __tablename__ = "friend_requests"
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    to_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    greeting = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at = db.Column(db.DateTime)
    # 收件人是否已查看（用于「新的研友」小红点：打开请求页即清零）
    is_seen = db.Column(db.Boolean, default=False)


class Friendship(db.Model):
    __tablename__ = "friendships"
    id = db.Column(db.Integer, primary_key=True)
    user_low_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user_high_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_low_id", "user_high_id"),)


class Skip(db.Model):
    __tablename__ = "skips"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    skipped_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "skipped_user_id"),)


class Conversation(db.Model):
    __tablename__ = "conversations"
    id = db.Column(db.Integer, primary_key=True)
    user_a_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user_b_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    source_tag_id = db.Column(db.Integer, db.ForeignKey("tags.id"))
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    __table_args__ = (db.UniqueConstraint("user_a_id", "user_b_id"),)


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_read = db.Column(db.Boolean, default=False)


class Thought(db.Model):
    __tablename__ = "thoughts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    body = db.Column(db.String(500), nullable=False)
    visibility = db.Column(db.String(16), nullable=False, default="public")  # public / friends / self
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class ThoughtTag(db.Model):
    __tablename__ = "thought_tags"
    id = db.Column(db.Integer, primary_key=True)
    thought_id = db.Column(db.Integer, db.ForeignKey("thoughts.id"), nullable=False, index=True)
    tag_id = db.Column(db.Integer, db.ForeignKey("tags.id"), nullable=False)


class Like(db.Model):
    __tablename__ = "likes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    thought_id = db.Column(db.Integer, db.ForeignKey("thoughts.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "thought_id"),)


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    thought_id = db.Column(db.Integer, db.ForeignKey("thoughts.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ExpLog(db.Model):
    """修炼值流水。每次获得修炼值记一条，用于「今日修炼进展」。

    kind: thought(发布随想) / like(被点赞) / liked(被标为喜欢) / invite(邀请成功)
    """

    __tablename__ = "exp_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(16), nullable=False, index=True)
    desc = db.Column(db.String(80))
    ref_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class AdminNotice(db.Model):
    """管理员操作通知（删除随想 / 删除评价时附理由，以对话形式发给用户）。"""

    __tablename__ = "admin_notices"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    # thought_deleted / review_deleted
    kind = db.Column(db.String(24), nullable=False)
    title = db.Column(db.String(80), nullable=False)
    reason = db.Column(db.String(300))
    snippet = db.Column(db.String(200))  # 被删内容的摘要
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_read = db.Column(db.Boolean, default=False)
