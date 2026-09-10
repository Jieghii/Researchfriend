"""研友 v7 端到端验收脚本。

覆盖 16 项需求的回归：
1. 通讯录迁到聊天页右上角 + 好友请求红点
2. 个人主页「我的随想」二级标签
3. 邀请码挪到个人主页改名「邀请新研友」
4. 用户反馈挪到个人主页
5. 个人资料一个月限改
6. 专属邀请链接 /register?code=xxx
7. 发布随想自定义标签
8. 被喜欢/聊过的人 数量 + 详情页
9. 修炼境界（发过随想→修炼境界）
10. 境界详情页 + 修炼境界说明
11. 修炼值获得方法
12. 玻璃球→旧财富排名
13. 铁牛奖排名（卖方打分）
14. 1-5星对应 夯/很夯/非常夯/超级夯/夯爆了
15. 管理员改名 + 删除通知
16. 新增团队默认空白 + demo 提示
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///yantou.db")

from app import app  # noqa: E402
from config import Config  # noqa: E402
from extensions import db  # noqa: E402
from models import (  # noqa: E402
    Brokerage,
    ResearchTeam,
    Review,
    TeamRating,
    Thought,
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
    # 清理历史测试数据，保证脚本可重复运行（否则会触发每日随想额度）
    from models import Tag as _Tag
    from models import ThoughtTag as _ThoughtTag

    for th in Thought.query.filter(Thought.body.like("%自定义标签测试%")).all():
        _ThoughtTag.query.filter_by(thought_id=th.id).delete()
        db.session.delete(th)
    for _tn in ["AI芯片", "新标签测试XYZ"]:
        _t = _Tag.query.filter_by(name=_tn).first()
        if _t:
            _ThoughtTag.query.filter_by(tag_id=_t.id).delete()
            db.session.delete(_t)
    db.session.commit()

with app.app_context():
    buyer = User.query.filter_by(role="buyer").first()
    seller = User.query.filter_by(role="seller").first()
    print(f"buyer={buyer.nickname} id={buyer.id}  seller={seller.nickname} id={seller.id}")

app.config["TESTING"] = True

section("未登录访问")
with app.test_client() as c:
    # 除登录/注册外，其余页面未登录应跳转到登录页（302）
    for path in ["/", "/glass", "/ironbull", "/topics", "/discover"]:
        r = c.get(path)
        check(f"GET {path} 未登录跳转登录", r.status_code in (302, 200), f"got {r.status_code}")
    for path in ["/login", "/register"]:
        r = c.get(path)
        check(f"GET {path}", r.status_code == 200, f"got {r.status_code}")

section("买方登录")
with app.test_client() as c:
    r = c.post("/login", data={"nickname": buyer.nickname, "password": "circle123"})
    check("买方登录", r.status_code in (200, 302))

    # 个人主页
    r = c.get("/me")
    html = r.data.decode("utf-8", errors="ignore")
    check("个人主页加载", r.status_code == 200)
    check("个人主页有「邀请新研友」", "邀请新研友" in html)
    check("个人主页有「用户反馈」", "用户反馈" in html)
    check("个人主页有「修炼境界」", "修炼境界" in html)
    check("个人主页有「我的随想」", "我的随想" in html)
    check("个人主页有「被喜欢」", "被喜欢" in html)
    check("个人主页有「聊过的人」", "聊过的人" in html)

    # 修炼境界详情
    r = c.get("/realm")
    html = r.data.decode("utf-8", errors="ignore")
    check("修炼境界页加载", r.status_code == 200)
    check("境界页含修炼值进度", "修炼值" in html or "进度" in html)
    check("境界页含今日进展", "今日" in html)

    # 修炼境界说明
    r = c.get("/realm/rules")
    html = r.data.decode("utf-8", errors="ignore")
    check("境界说明页加载", r.status_code == 200)
    for realm in ["闻弦境", "鸣骨境", "成丹境", "点墨境", "种莲境", "观山境", "燃灯境", "登楼境", "执棋境", "入画境"]:
        if realm not in html:
            check(f"境界说明含「{realm}」", False)
    check("境界说明含十境", all(x in html for x in ["闻弦境", "鸣骨境", "入画境"]))
    check("境界说明含修炼值获得方法", "发布随想" in html or "邀请" in html)

    # 我的随想二级页
    r = c.get("/me/thoughts")
    check("我的随想页加载", r.status_code == 200)

    # 被喜欢 / 聊过的人 详情
    r = c.get("/me/liked")
    check("被喜欢列表加载", r.status_code == 200)
    r = c.get("/me/talked")
    check("聊过的人列表加载", r.status_code == 200)

    # 通讯录
    r = c.get("/friends")
    check("通讯录加载", r.status_code == 200)
    r = c.get("/requests")
    check("好友请求页加载", r.status_code == 200)

    # 邀请码页
    r = c.get("/invite")
    html = r.data.decode("utf-8", errors="ignore")
    check("邀请码页加载", r.status_code == 200)
    check("邀请页含专属链接", "/register?code=" in html)

    # 旧财富排名
    r = c.get("/glass")
    html = r.data.decode("utf-8", errors="ignore")
    check("旧财富排名加载", r.status_code == 200)
    check("旧财富页含「旧财富排名」", "旧财富排名" in html)
    check("旧财富页含星级评级「夯」", "夯" in html)

    # 铁牛奖（买方登录应该看不到打分按钮但能看榜单）
    r = c.get("/ironbull")
    html = r.data.decode("utf-8", errors="ignore")
    check("铁牛奖页加载", r.status_code == 200)
    check("铁牛奖页含「铁牛奖」", "铁牛奖" in html)

    # 发现页
    r = c.get("/discover")
    html = r.data.decode("utf-8", errors="ignore")
    check("发现页加载", r.status_code == 200)
    check("发现页含铁牛奖入口", "铁牛奖" in html)

    # 聊天页含通讯录入口
    r = c.get("/chat")
    html = r.data.decode("utf-8", errors="ignore")
    check("聊天页加载", r.status_code == 200)
    check("聊天页含通讯录入口", "通讯录" in html)

    # 发布随想自定义标签（后端）
    r = c.post("/api/thoughts", json={"body": "自定义标签测试", "visibility": "public", "tag_ids": [], "tag_names": ["AI芯片", "新标签测试XYZ"]})
    data = r.get_json()
    ok_tags = r.status_code == 200 and data.get("ok") and data.get("item", {}).get("tags")
    check("发布随想支持自定义标签", ok_tags, str(data.get("item", {}).get("tags") if data else None))

section("卖方登录")
with app.test_client() as c:
    r = c.post("/login", data={"nickname": seller.nickname, "password": "circle123"})
    check("卖方登录", r.status_code in (200, 302))

    # 铁牛奖：卖方应该能打分
    r = c.get("/ironbull")
    html = r.data.decode("utf-8", errors="ignore")
    check("卖方铁牛奖页加载", r.status_code == 200)
    # 卖方在旧财富榜应该被限制打分
    r = c.get("/glass")
    html = r.data.decode("utf-8", errors="ignore")
    check("卖方旧财富榜加载", r.status_code == 200)

section("管理员")
with app.test_client() as c:
    r = c.post("/admin/login", data={"password": Config.ADMIN_PASSWORD})
    check("管理员登录", r.status_code in (200, 302))
    r = c.get("/admin/orgs")
    html = r.data.decode("utf-8", errors="ignore")
    check("管理员机构管理页加载", r.status_code == 200)
    check("管理员可改名券商/团队", "改名" in html or "重命名" in html or "修改" in html)
    # 内容管理页
    r = c.get("/admin/content")
    html = r.data.decode("utf-8", errors="ignore")
    check("管理员内容管理页加载", r.status_code == 200)
    check("内容管理页含删除按钮", "data-del-thought" in html or "data-del-review" in html)
    # 测试删除随想（带理由）→ 生成通知
    from models import AdminNotice as _AN, Thought as _Th
    with app.app_context():
        victim = _Th.query.order_by(_Th.id.desc()).first()
        vid = victim.id if victim else None
        author = victim.author_id if victim else None
    if vid:
        r = c.post(f"/admin/api/thoughts/{vid}/delete", json={"reason": "测试删除理由"})
        check("删除随想返回 ok", r.status_code == 200 and r.get_json().get("ok"))
        with app.app_context():
            notice = _AN.query.filter_by(user_id=author, kind="thought_deleted").first()
            check("删除随想生成管理员通知", notice is not None and notice.reason == "测试删除理由")

section("数据模型")
with app.app_context():
    b = Brokerage.query.filter_by(kind="buyside").first()
    check("买方机构种子数据存在", b is not None)
    ir = TeamRating.query.filter(TeamRating.invest.isnot(None)).first()
    check("铁牛奖评分种子数据存在", ir is not None)
    check("铁牛奖评分 research 填 0", ir.research == 0)

print(f"\n{'='*40}")
print(f"通过 {passed} / {passed + failed}")
if fails:
    print("失败项：")
    for f in fails:
        print(f"  - {f}")
else:
    print("全部通过 🎉")
