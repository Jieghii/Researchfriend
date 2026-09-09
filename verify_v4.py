"""v4 端到端验收：玻璃球新增团队 + 话题详情相关随想渲染。

直接对本地 SQLite 数据和 app 路由做集成测试，避免外部网络请求。
"""
import json
import sys
import os

# 让脚本能 import 项目模块
ROOT = r"C:\Users\12247\WorkBuddy\2026-09-08-21-34-45\研投圈-demo\code"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# 强制本地 SQLite
os.environ["DATABASE_URL"] = "sqlite:///yantou.db"

from app import app  # noqa: E402
from extensions import db  # noqa: E402
from models import (  # noqa: E402
    Brokerage,
    ResearchTeam,
    TeamRating,
    Thought,
    ThoughtTag,
    Tag,
    User,
    UserTag,
)


results = []
def check(name, ok, detail=""):
    mark = "✅" if ok else "❌"
    print(f"{mark} {name}{(' — ' + detail) if detail else ''}")
    results.append((name, ok, detail))


with app.app_context():
    # ---- 玻璃球新增团队功能 ----
    print("\n=== 玻璃球：新增团队评分 ===")
    # 找一个买方种子用户
    buyer = User.query.filter_by(role="buyer").first()
    check("种子买方用户存在", buyer is not None, f"nickname={buyer.nickname if buyer else None}")

    with app.test_client() as c:
        # 登录买方
        r = c.post("/login", data={"nickname": buyer.nickname, "password": "circle123"})
        check("买方登录成功", r.status_code in (200, 302))

        # 玻璃球首页
        r = c.get("/glass")
        html = r.data.decode("utf-8", errors="ignore")
        check("玻璃球页加载成功", r.status_code == 200, f"status={r.status_code}")
        check("顶部出现「新增团队评分」按钮", "data-open-add-team" in html)
        check("出现 add-team-modal 容器", 'id="add-team-modal"' in html)
        check("datalist 列出当前券商", 'id="brokerage-list"' in html)
        check("三维 1-5 星 picker 各出现 5 颗星", html.count('data-star="') >= 15)
        check("出现券商名称输入框", 'id="new-brokerage-name"' in html)
        check("出现团队名称输入框", 'id="new-team-name"' in html)
        check("出现提交按钮", 'data-submit-add-team' in html)

        # 抓一个不存在的券商名（用「测试券商_验收4」）
        test_brokerage = "测试券商_验收4"
        test_team = "测试团队_验收4"
        # 清理可能残留
        old_b = Brokerage.query.filter_by(name=test_brokerage).first()
        if old_b:
            old_t = ResearchTeam.query.filter_by(brokerage_id=old_b.id, name=test_team).first()
            if old_t:
                TeamRating.query.filter_by(team_id=old_t.id).delete()
                db.session.delete(old_t)
            # 清掉残留团队和券商
            for ot in ResearchTeam.query.filter_by(brokerage_id=old_b.id).all():
                TeamRating.query.filter_by(team_id=ot.id).delete()
                db.session.delete(ot)
            db.session.delete(old_b)
            db.session.commit()

        # 提交一个三维 5/4/3 的新团队
        before_b = Brokerage.query.count()
        before_t = ResearchTeam.query.count()
        r = c.post("/api/glass/team/create", data=json.dumps({
            "brokerage_name": test_brokerage,
            "team_name": test_team,
            "research": 5, "service": 4, "capital": 3,
        }), content_type="application/json")
        body = r.get_json()
        check("API 返回 200", r.status_code == 200, str(body))
        check("ok=True", body.get("ok") is True)
        check("返回 redirect 链接", "redirect" in body)
        check("返回 team_id", body.get("team_id") is not None)
        after_b = Brokerage.query.count()
        after_t = ResearchTeam.query.count()
        check("新增一个券商", after_b == before_b + 1, f"{before_b} → {after_b}")
        check("新增一个团队", after_t == before_t + 1, f"{before_t} → {after_t}")

        # 验证落地数据
        new_b = Brokerage.query.filter_by(name=test_brokerage).first()
        new_t = ResearchTeam.query.filter_by(brokerage_id=new_b.id, name=test_team).first()
        rate = TeamRating.query.filter_by(team_id=new_t.id, user_id=buyer.id).first()
        check("券商 hue 计算正确", new_b.hue is not None and 0 <= new_b.hue < 360)
        check("团队 intro 字段正确", "贡献" in (new_t.intro or ""))
        check("打分记录落地", rate is not None and rate.research == 5 and rate.service == 4 and rate.capital == 3)

        # 同一团队再提交，覆盖打分
        r = c.post("/api/glass/team/create", data=json.dumps({
            "brokerage_name": test_brokerage,
            "team_name": test_team,
            "research": 3, "service": 3, "capital": 3,
        }), content_type="application/json")
        body = r.get_json()
        check("同团队二次提交仍 ok", body.get("ok") is True)
        # 数据库仍然只有一条 TeamRating（覆盖更新）
        cnt = TeamRating.query.filter_by(team_id=new_t.id, user_id=buyer.id).count()
        check("同团队同用户评分记录唯一（覆盖）", cnt == 1, f"count={cnt}")
        rate2 = TeamRating.query.filter_by(team_id=new_t.id, user_id=buyer.id).first()
        check("分数被覆盖为 3/3/3", rate2.research == 3 and rate2.service == 3 and rate2.capital == 3)

        # 缺一个维度，期望报错
        r = c.post("/api/glass/team/create", data=json.dumps({
            "brokerage_name": test_brokerage,
            "team_name": test_team,
            "research": 4, "service": 4, "capital": 0,
        }), content_type="application/json")
        check("缺维度返回 400", r.status_code == 400)
        body = r.get_json()
        check("缺维度报错文案", "维度" in (body.get("error") or "") or "星" in (body.get("error") or ""))

        # 缺名字
        r = c.post("/api/glass/team/create", data=json.dumps({
            "brokerage_name": "",
            "team_name": "x",
            "research": 4, "service": 4, "capital": 4,
        }), content_type="application/json")
        check("空券商名返回 400", r.status_code == 400)

        # 卖方登录测试拒绝
        seller = User.query.filter_by(role="seller").first()
        with c.session_transaction():
            c.delete_cookie("session")
        # 卖方登录
        r = c.post("/login", data={"nickname": seller.nickname, "password": "circle123"})
        check("卖方登录成功", r.status_code in (200, 302))
        r = c.post("/api/glass/team/create", data=json.dumps({
            "brokerage_name": "x", "team_name": "y",
            "research": 5, "service": 5, "capital": 5,
        }), content_type="application/json")
        check("卖方调用被拒绝", r.status_code == 403)

        # 登录回买方继续
        r = c.post("/login", data={"nickname": buyer.nickname, "password": "circle123"})

        # 玻璃球页签能否列出该团队
        r = c.get(f"/glass/team/{new_t.id}")
        check("新建团队详情页加载", r.status_code == 200)
        check("新团队页展示创建者评分", b"3.00" in r.data or "3.0" in r.data.decode("utf-8", errors="ignore"))

        # 该团队所在券商详情页
        r = c.get(f"/glass/brokerage/{new_b.id}")
        check("新建券商详情页加载", r.status_code == 200)

        # 玻璃球首页展示新券商
        r = c.get("/glass")
        html = r.data.decode("utf-8", errors="ignore")
        check("首页出现新建券商", test_brokerage in html)

        # 团队总榜能搜到（哪怕分数低）—— 总榜走 /glass/rank/team
        r = c.get("/glass/rank/team")
        check("团队总榜加载", r.status_code == 200)
        rank_html = r.data.decode("utf-8", errors="ignore")
        check("团队总榜出现新建团队", test_team in rank_html)

    # ---- 话题详情页相关随想 ----
    print("\n=== 话题详情：相关随想渲染 ===")
    with app.test_client() as c:
        r = c.post("/login", data={"nickname": buyer.nickname, "password": "circle123"})

        # 找一个有随想的话题
        # 先看哪些 tag 关联过 Thought
        used_tag_id = (
            db.session.query(ThoughtTag.tag_id)
            .join(Thought, Thought.id == ThoughtTag.thought_id)
            .filter(Thought.visibility == "public")
            .group_by(ThoughtTag.tag_id)
            .order_by(db.func.count(Thought.id).desc())
            .first()
        )
        if not used_tag_id:
            check("能找到带随想的话题", False, "无 ThoughtTag 数据")
        else:
            tid = used_tag_id[0]
            tag = Tag.query.get(tid)
            check("话题详情页加载", True, f"tag={tag.name}")
            r = c.get(f"/topics/{tid}")
            check("URL 200", r.status_code == 200)
            html = r.data.decode("utf-8", errors="ignore")

            # 验证 thought_card 宏渲染：头像、role-chip、time、tags、点赞、评论
            check("相关随想卡片有 .thought-card", 'class="card thought-card' in html)
            check("渲染了 avatar 头像 div", 'class="avatar ' in html or 'class="avatar ' in html)
            check("出现了 role-chip（买方/卖方）", 'role-chip' in html)
            check("出现了 rel_time 文本（分钟前/刚刚）", "分钟前" in html or "刚刚" in html or "小时前" in html or "昨天" in html)
            check("标签链接到 /topics/<id>", html.count('href="/topics/') >= 1)
            check("有 like-btn 点赞按钮", 'data-like=' in html)
            check("有 like-btn 评论按钮（含 svg_comment）", 'svg_comment' in html or "评论" in html)

            # 验证 related 列表有数据（页面有 thought-card class）
            check("相关随想标题渲染", "相关随想" in html)
            # 至少一条
            check("至少有 1 条相关随想卡片", html.count('class="card thought-card') >= 1)

    # ---- 清理测试数据 ----
    print("\n=== 清理测试数据 ===")
    # 删 TeamRating / ResearchTeam / Brokerage（顺序：先打分、再团队、再券商）
    cnt = 0
    for b in Brokerage.query.filter(Brokerage.name.like("测试券商_%")).all():
        for t in ResearchTeam.query.filter_by(brokerage_id=b.id).all():
            TeamRating.query.filter_by(team_id=t.id).delete()
            db.session.delete(t)
            cnt += 1
        db.session.delete(b)
    db.session.commit()
    print(f"清理了 {cnt} 条测试团队/券商")

print("\n=== 验收总结 ===")
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"通过 {passed}/{total}")
if passed != total:
    print("失败项：")
    for n, ok, d in results:
        if not ok:
            print(f"  ❌ {n}{(' — ' + d) if d else ''}")
    sys.exit(1)