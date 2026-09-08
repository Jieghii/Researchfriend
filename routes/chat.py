from datetime import timedelta

from flask import Blueprint, jsonify, render_template, request

from extensions import db
from models import Conversation, FriendRequest, Message, Tag, User
from routes.auth import current_user
from services import (
    are_friends,
    conversation_inbox,
    format_msg_time,
    get_or_create_conversation,
    mark_conversation_read,
    now_utc,
    pending_from_me,
    pending_to_me,
    user_brief,
)

bp = Blueprint("chat", __name__)


@bp.route("/chat")
def inbox():
    me = current_user()
    return render_template("chats.html", nav="chat", items=conversation_inbox(me))


def _peer(conv, me_id):
    pid = conv.user_b_id if conv.user_a_id == me_id else conv.user_a_id
    return User.query.get(pid)


@bp.route("/chat/<int:user_id>")
def page(user_id):
    me = current_user()
    if user_id == me.id:
        return jsonify({"error": "不能和自己聊"}), 400
    peer = User.query.get_or_404(user_id)
    tag_id = request.args.get("topic", type=int)
    conv = get_or_create_conversation(me.id, peer.id, source_tag_id=tag_id)
    source = Tag.query.get(conv.source_tag_id) if conv.source_tag_id else None
    friends = are_friends(me.id, peer.id)
    pending_sent = user_id in pending_from_me(me.id)
    pending_recv = user_id in pending_to_me(me.id)
    msgs = (
        Message.query.filter_by(conversation_id=conv.id).order_by(Message.id.asc()).limit(200).all()
    )
    mark_conversation_read(conv.id, me.id)
    return render_template(
        "chat.html",
        nav="chat",
        conv=conv,
        peer=user_brief(peer, me),
        source=source,
        friends=friends,
        pending_sent=pending_sent,
        pending_recv=pending_recv,
        messages=[_msg_json(m, me.id, msgs) for m in msgs],
        last_id=msgs[-1].id if msgs else 0,
    )


def _msg_json(m, me_id, all_msgs=None):
    show_meta = True
    if all_msgs:
        idx = all_msgs.index(m) if m in all_msgs else -1
        if idx > 0:
            prev = all_msgs[idx - 1]
            if prev.sender_id == m.sender_id and (m.created_at - prev.created_at) < timedelta(minutes=30):
                show_meta = False
    sep = None
    if all_msgs:
        idx = all_msgs.index(m) if m in all_msgs else 0
        if idx == 0 or (m.created_at - all_msgs[idx - 1].created_at) >= timedelta(minutes=30):
            sep = format_msg_time(m.created_at)
    return {
        "id": m.id,
        "mine": m.sender_id == me_id,
        "content": m.content,
        "created_at": m.created_at.isoformat() + "Z",
        "show_meta": show_meta,
        "sep": sep,
    }


@bp.route("/api/chat/<int:conv_id>/poll")
def poll(conv_id):
    me = current_user()
    conv = Conversation.query.get_or_404(conv_id)
    if me.id not in (conv.user_a_id, conv.user_b_id):
        return jsonify({"ok": False}), 403
    after = int(request.args.get("after") or 0)
    mark_conversation_read(conv_id, me.id)
    rows = (
        Message.query.filter(Message.conversation_id == conv_id, Message.id > after)
        .order_by(Message.id.asc())
        .limit(50)
        .all()
    )
    prev = Message.query.filter_by(conversation_id=conv_id).filter(Message.id <= after).order_by(Message.id.desc()).first()
    packed = []
    seq = ([prev] if prev else []) + rows
    for m in rows:
        packed.append(_msg_json(m, me.id, seq))
    return jsonify({"messages": packed})


@bp.route("/api/chat/<int:conv_id>/send", methods=["POST"])
def send(conv_id):
    me = current_user()
    conv = Conversation.query.get_or_404(conv_id)
    if me.id not in (conv.user_a_id, conv.user_b_id):
        return jsonify({"ok": False}), 403
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("content") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "空消息不能发送"}), 400
    if len(text) > 500:
        return jsonify({"ok": False, "error": "单条最多 500 字"}), 400
    m = Message(conversation_id=conv.id, sender_id=me.id, content=text, created_at=now_utc(), is_read=True)
    conv.last_message_at = m.created_at
    db.session.add(m)
    db.session.commit()
    return jsonify({"ok": True, "message": _msg_json(m, me.id)})


@bp.route("/api/chat/<int:user_id>/add-friend", methods=["POST"])
def add_friend(user_id):
    me = current_user()
    if user_id == me.id:
        return jsonify({"ok": False}), 400
    if are_friends(me.id, user_id):
        return jsonify({"ok": True, "friends": True})
    if FriendRequest.query.filter_by(from_user_id=me.id, to_user_id=user_id, status="pending").first():
        return jsonify({"ok": True, "pending": True})
    existing = FriendRequest.query.filter_by(from_user_id=user_id, to_user_id=me.id, status="pending").first()
    if existing:
        from routes.profile import accept_request_logic

        accept_request_logic(me, existing)
        return jsonify({"ok": True, "friends": True})
    db.session.add(
        FriendRequest(
            from_user_id=me.id,
            to_user_id=user_id,
            greeting="我们可以加个好友继续聊。",
            status="pending",
            created_at=now_utc(),
        )
    )
    db.session.commit()
    return jsonify({"ok": True, "pending": True})
