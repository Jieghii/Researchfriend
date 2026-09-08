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
