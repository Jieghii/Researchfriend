"""研友 v8 端到端验收脚本：5 项改动
1. 好友请求红点移到聊天 tab
2. 管理员可删除/编辑机构与团队（含简介）
3. 聊天收件箱保留未读红点
4. 旧财富/铁牛奖详情页加返回按钮
5. 团队详情页不展示简介
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///yantou.db")

from app import app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models import (  # noqa: E402
    Brokerage,
    Conversation,
    Message,
    ResearchTeam,
    Review,
    TeamRating,
    User,
)

passed = 0
failed = 0
fails = []


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        fails.append(name)
        print(f"  ❌ {name}  {extra}")


def section(title):
    print(f"\n=== {title} ===")


with app.app_context():
    buyer = User.query.filter_by(role="buyer").first()
    seller = User.query.filter_by(role="seller").first()
    print(f"buyer={buyer.nickname} id={buyer.id}  seller={seller.nickname} id={seller.id}")

app.config["TESTING"] = True


# ============ 需求 1：好友请求红点移到聊天 tab ============
section("需求1：好友请求红点移到聊天 tab")
import re as _re

base_src = open("templates/base.html", encoding="utf-8").read()
# 取「聊天」a 标签那一行：聊天 + chat_unread badge + pending_count badge
chat_lines = [ln for ln in base_src.splitlines() if "聊天" in ln and "url_for('chat.inbox')" in ln]
me_lines = [ln for ln in base_src.splitlines() if "我的" in ln and "url_for('profile.me_page')" in ln]
check("桌面聊天 tab 含 pending_count 红点",
      any("pending_count" in ln for ln in chat_lines),
      extra=f"chat_lines={chat_lines[:2]}")
check("桌面「我的」tab 不含 pending_count 红点",
      not any("pending_count" in ln for ln in me_lines),
      extra=f"me_lines={me_lines[:2]}")
# 移动端（mobile-tab 区域）
mobile_chat = [ln for ln in base_src.splitlines() if "聊天" in ln and "url_for('chat.inbox')" in ln and "nav-item" not in ln]
mobile_me = [ln for ln in base_src.splitlines() if "我的" in ln and "url_for('profile.me_page')" in ln and "nav-item" not in ln]
check("移动端聊天 tab 含 pending_count 红点",
      any("pending_count" in ln for ln in mobile_chat),
      extra=f"mobile_chat={mobile_chat[:2]}")
check("移动端「我的」tab 不含 pending_count 红点",
      not any("pending_count" in ln for ln in mobile_me),
      extra=f"mobile_me={mobile_me[:2]}")


# ============ 需求 2：管理员可删除/编辑机构与团队 ============
section("需求2：管理员删除机构/团队 + 修改简介")
# 通过 admin_required 装饰器不可绕过，直接用 admin_required 但 session 注入即可

with app.app_context():
    org = Brokerage.query.filter_by(kind="brokerage").first()
    team = ResearchTeam.query.filter_by(brokerage_id=org.id).first() if org else None
    print(f"  target org={org.name if org else 'NONE'} team={team.name if team else 'NONE'}")
    # 提前取出 id（避免在 test_client 内再用 query 触发 context 问题）
    org_id = org.id if org else None
    team_id = team.id if team else None

with app.test_client() as c:
    with c.session_transaction() as sess:
        sess["admin_ok"] = True

    # 2a: update org（改简介 + 名字）
    if org_id:
        new_intro = "v8 test intro"
        r = c.post(f"/admin/api/orgs/{org_id}/update", json={"name": org.name, "intro": new_intro})
        check("update org 改简介返回 ok", r.is_json and r.json.get("ok") is True, extra=str(r.json))
        with app.app_context():
            o = Brokerage.query.get(org_id)
            check("org.intro 已写入数据库", o.intro == new_intro, extra=f"intro={o.intro}")

    # 2b: update team（改简介）
    if team_id:
        new_intro_t = "v8 test team intro"
        r = c.post(f"/admin/api/teams/{team_id}/update", json={"name": team.name, "intro": new_intro_t})
        check("update team 改简介返回 ok", r.is_json and r.json.get("ok") is True, extra=str(r.json))
        with app.app_context():
            t = ResearchTeam.query.get(team_id)
            check("team.intro 已写入数据库", t.intro == new_intro_t, extra=f"intro={t.intro}")

# 2c: 创建一个临时 team 用于删除测试（避免污染种子数据）
with app.app_context():
    temp_team = ResearchTeam(brokerage_id=org_id, name="__v8_delete_test__", intro="to be deleted")
    db.session.add(temp_team)
    db.session.commit()
    tid = temp_team.id
    db.session.add(TeamRating(team_id=tid, user_id=buyer.id, research=3, service=3, capital=3))
    db.session.add(Review(target_type="team", target_id=tid, author_id=buyer.id, content="test review"))
    db.session.commit()

with app.test_client() as c:
    with c.session_transaction() as sess:
        sess["admin_ok"] = True
    r = c.post(f"/admin/api/teams/{tid}/delete")
    check("delete team 返回 ok", r.is_json and r.json.get("ok") is True, extra=str(r.json))

with app.app_context():
    check("team 已被删除", ResearchTeam.query.get(tid) is None)
    check("team 的 TeamRating 已被级联删除", TeamRating.query.filter_by(team_id=tid).count() == 0)
    check("team 的 Review 已被级联删除", Review.query.filter_by(target_type="team", target_id=tid).count() == 0)

# 2d: 临时创建一个临时机构用于删除测试
with app.app_context():
    existing_names = {b.name for b in Brokerage.query.all()}
    candidate = f"__v8_test_org_{os.getpid()}"
    if candidate not in existing_names:
        temp_org = Brokerage(name=candidate, short_name="TT", kind="brokerage", intro="to be deleted")
        db.session.add(temp_org)
        db.session.commit()
        temp_oid = temp_org.id
        # 加下属 team + 评分 + 评价
        tmp_team = ResearchTeam(brokerage_id=temp_oid, name="tt", kind="brokerage")
        db.session.add(tmp_team)
        db.session.commit()
        tmp_team_id = tmp_team.id
        db.session.add(TeamRating(team_id=tmp_team_id, user_id=buyer.id, research=2, service=2, capital=2))
        db.session.add(Review(target_type="team", target_id=tmp_team_id, author_id=buyer.id, content="rt"))
        db.session.add(Review(target_type="brokerage", target_id=temp_oid, author_id=buyer.id, content="ro"))
        db.session.commit()
    else:
        temp_oid = None

if temp_oid:
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["admin_ok"] = True
        r = c.post(f"/admin/api/orgs/{temp_oid}/delete")
        check("delete org 返回 ok", r.is_json and r.json.get("ok") is True, extra=str(r.json))

    with app.app_context():
        check("org 已被删除", Brokerage.query.get(temp_oid) is None)
        check("org 下属 team 已被级联删除", ResearchTeam.query.filter_by(brokerage_id=temp_oid).count() == 0)
        check("对 org 的 Review 已被级联删除",
              Review.query.filter_by(target_type="brokerage", target_id=temp_oid).count() == 0)


# 清理：把测试中改过的种子数据 intro 还原
with app.app_context():
    if org_id:
        o = Brokerage.query.get(org_id)
        if o and o.intro == "v8 test intro":
            o.intro = None
    if team_id:
        t = ResearchTeam.query.get(team_id)
        if t and t.intro == "v8 test team intro":
            t.intro = None
    db.session.commit()


# ============ 需求 3：聊天收件箱保留未读红点 ============
section("需求3：聊天收件箱保留未读红点")
with app.app_context():
    # 清理测试数据
    me_id = buyer.id
    other_id = seller.id
    conv = Conversation.query.filter(
        ((Conversation.user_a_id == me_id) & (Conversation.user_b_id == other_id))
        | ((Conversation.user_a_id == other_id) & (Conversation.user_b_id == me_id))
    ).first()
    if not conv:
        conv = Conversation(user_a_id=me_id, user_b_id=other_id)
        db.session.add(conv)
        db.session.commit()
    # 清空旧消息
    Message.query.filter_by(conversation_id=conv.id).delete()
    db.session.commit()
    # 卖方发给买方 3 条未读消息
    for i in range(3):
        db.session.add(Message(
            conversation_id=conv.id, sender_id=other_id,
            content=f"v8 test msg {i}", is_read=False,
        ))
    db.session.commit()
    cid = conv.id

# 买方登录查看聊天收件箱
with app.test_client() as c:
    r = c.post("/login", data={"nickname": buyer.nickname, "password": "circle123"}, follow_redirects=True)
    r = c.get("/chat")
    html = r.data.decode("utf-8")
    check("聊天收件箱页 200", r.status_code == 200, extra=f"status={r.status_code}")
    # chats.html 模板里 badge 写法：<span class="badge">{{ it.unread }}</span>
    check("聊天收件箱含未读数字红点 (badge 含 3)",
          'class="badge">3<' in html or 'class="badge">3</' in html,
          extra=f"片段：{html[html.find('chat-list'):html.find('chat-list')+500] if 'chat-list' in html else '未找到'}")
    # 关键验证：进入 inbox 后未读不应被清零
    with app.app_context():
        unread = Message.query.filter_by(conversation_id=cid, is_read=False).count()
        check("进入收件箱后未读消息未被清零", unread == 3, extra=f"unread={unread}")


# ============ 需求 4：榜单详情页返回按钮 ============
section("需求4：榜单详情页加返回按钮")
org_src = open("templates/board_org.html", encoding="utf-8").read()
team_src = open("templates/board_team.html", encoding="utf-8").read()
check("board_org.html 返回按钮用 btn-ghost 样式",
      'class="btn btn-ghost"' in org_src and "url_for('glass.index')" in org_src,
      extra="期望 btn btn-ghost + url_for('glass.index')")
check("board_team.html 返回按钮用 btn-ghost 样式",
      'class="btn btn-ghost"' in team_src and "url_for('glass.index')" in team_src,
      extra="期望 btn btn-ghost + url_for('glass.index')")
# 检查 team 详情页确实回到了榜单列表而非机构
check("board_team.html 返回链接指向 glass.index/ironbull（不是 org_detail）",
      "url_for('glass.org_detail'" not in team_src.split("返回")[1].split("\n")[0] if "返回" in team_src else True)


# ============ 需求 5：团队详情页不展示简介 ============
section("需求5：团队详情页不展示简介")
# board_team.html 应不渲染 team.intro
check("board_team.html 不渲染 team.intro",
      "team.intro" not in team_src.split("{{ team.name }}")[1].split("</section>")[0],
      extra="期望 team.name 后不含 team.intro")
# board_org.html 不受影响，仍展示 org.intro
org_src_after_h1 = org_src.split("<h1")[1].split("</section>")[0] if "<h1" in org_src else ""
check("board_org.html 仍展示 org.intro",
      "org.intro" in org_src_after_h1,
      extra="期望 org.intro 保留")


# ============ 收尾 ============
print()
print("=" * 50)
print(f"通过 {passed} / {passed + failed}")
if fails:
    print("失败：", ", ".join(fails))
else:
    print("全部通过 🎉")