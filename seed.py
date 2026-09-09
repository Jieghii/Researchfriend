"""首次启动写入预置用户与内容。可重复执行：已有用户则跳过。"""
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from extensions import db
from models import (
    Comment,
    Conversation,
    FriendRequest,
    Friendship,
    Like,
    Message,
    Tag,
    Thought,
    ThoughtTag,
    User,
    UserTag,
)
from services import PRESET_INDUSTRIES, PRESET_STOCKS, pair_ids

# 演示账号密码统一为 circle123（散列入库，禁止明文）。本项目为演示用途。
DEMO_PASSWORD = "circle123"

USERS = [
    {"nickname": "林知微", "role": "buyer", "years": "5-10年", "tags": ["白酒", "调味品", "贵州茅台", "五粮液", "海天味业"], "sig": "买方消费组，盯渠道库存和批价。"},
    {"nickname": "周衡", "role": "seller", "years": "5-10年", "tags": ["白酒", "半导体", "贵州茅台", "中芯国际"], "sig": "卖方食品饮料，覆盖白酒全链条。"},
    {"nickname": "沈予安", "role": "buyer", "years": "3-5年", "tags": ["半导体", "消费电子", "中芯国际"], "sig": "买方电子，看晶圆与封测稼动。"},
    {"nickname": "顾清越", "role": "seller", "years": "10-15年", "tags": ["半导体", "中芯国际", "消费电子"], "sig": "卖方电子首席，覆盖半导体设备材料。"},
    {"nickname": "叶晚宁", "role": "buyer", "years": "1-3年", "tags": ["新能源车", "光伏", "宁德时代", "比亚迪"], "sig": "买方制造，电车与锂电景气跟踪。"},
    {"nickname": "陆景行", "role": "seller", "years": "5-10年", "tags": ["新能源车", "储能", "宁德时代", "比亚迪"], "sig": "卖方电新，动力电池与储能。"},
    {"nickname": "苏晚晴", "role": "buyer", "years": "3-5年", "tags": ["光伏", "储能", "隆基绿能"], "sig": "买方新能源，组件排产和硅料价格。"},
    {"nickname": "韩北辰", "role": "seller", "years": "15年+", "tags": ["光伏", "隆基绿能", "储能"], "sig": "卖方电新老将，看海外装机。"},
    {"nickname": "程予舟", "role": "buyer", "years": "5-10年", "tags": ["医药", "CXO", "药明康德"], "sig": "买方医药，创新药临床与CXO订单。"},
    {"nickname": "方知夏", "role": "seller", "years": "3-5年", "tags": ["医药", "CXO", "药明康德"], "sig": "卖方医药，覆盖CXO与器械。"},
    {"nickname": "江澄", "role": "buyer", "years": "<1年", "tags": ["互联网", "港股互联网", "腾讯控股", "美团"], "sig": "买方TMT新人，看广告与本地生活。"},
    {"nickname": "裴昭", "role": "seller", "years": "5-10年", "tags": ["港股互联网", "腾讯控股", "美团", "互联网"], "sig": "卖方互联网，覆盖腾讯与美团。"},
    {"nickname": "白露", "role": "buyer", "years": "10-15年", "tags": ["银行", "地产", "保险"], "sig": "买方金融，银行净息差与地产链。"},
    {"nickname": "秦牧", "role": "seller", "years": "10-15年", "tags": ["银行", "地产"], "sig": "卖方金融地产联席。"},
    {"nickname": "谢听潮", "role": "buyer", "years": "1-3年", "tags": ["军工", "半导体", "中芯国际"], "sig": "买方军工，信息化与上游芯片。"},
    {"nickname": "任晚舟", "role": "seller", "years": "3-5年", "tags": ["军工", "半导体"], "sig": "卖方军工，主机厂与配套。"},
    {"nickname": "赵观澜", "role": "buyer", "years": "5-10年", "tags": ["啤酒", "乳制品", "调味品", "海天味业"], "sig": "买方食品，啤酒吨价与乳制品原奶。"},
    {"nickname": "吴栖迟", "role": "seller", "years": "1-3年", "tags": ["啤酒", "白酒", "调味品"], "sig": "卖方食品饮料助理分析师。"},
    {"nickname": "唐青瓷", "role": "buyer", "years": "3-5年", "tags": ["消费电子", "新能源车", "比亚迪"], "sig": "买方制造，消费电子与智能驾驶。"},
    {"nickname": "何远山", "role": "seller", "years": "5-10年", "tags": ["消费电子", "半导体"], "sig": "卖方硬件，果链与安卓品牌。"},
    {"nickname": "梁小满", "role": "buyer", "years": "<1年", "tags": ["白酒", "贵州茅台", "光伏"], "sig": "买方新人，白酒入门兼看光伏。"},
    {"nickname": "尹南风", "role": "seller", "years": "15年+", "tags": ["医药", "创新药", "药明康德"], "sig": "卖方医药老将，看管线定价。"},
    {"nickname": "曹见山", "role": "buyer", "years": "10-15年", "tags": ["储能", "光伏", "新能源车", "宁德时代"], "sig": "买方产业，储能招标与锂电排产。"},
    {"nickname": "宋以宁", "role": "seller", "years": "3-5年", "tags": ["乳制品", "调味品", "海天味业"], "sig": "卖方必选消费。"},
    {"nickname": "冯疏影", "role": "buyer", "years": "1-3年", "tags": ["互联网", "美团", "消费电子"], "sig": "买方互联网，本地生活与硬件交叉。"},
    {"nickname": "蒋栖梧", "role": "seller", "years": "5-10年", "tags": ["地产", "银行", "白酒"], "sig": "卖方宏观策略转行业，看地产后周期。"},
    {"nickname": "许清和", "role": "buyer", "years": "5-10年", "tags": ["CXO", "医药", "半导体"], "sig": "买方医药+电子交叉覆盖。"},
    {"nickname": "郑北野", "role": "seller", "years": "1-3年", "tags": ["新能源车", "比亚迪", "宁德时代", "光伏"], "sig": "卖方电新，车企销量跟踪。"},
]

FRIEND_PAIRS = [
    ("林知微", "周衡"),
    ("林知微", "赵观澜"),
    ("沈予安", "顾清越"),
    ("叶晚宁", "陆景行"),
    ("苏晚晴", "韩北辰"),
    ("程予舟", "方知夏"),
    ("江澄", "裴昭"),
    ("曹见山", "陆景行"),
    ("许清和", "方知夏"),
]

THOUGHTS = [
    ("周衡", "渠道反馈端午后动销略好于预期，但库存仍偏高，批价想快速回升不现实。更关键的是看三季度宴席恢复斜率。", "public", ["白酒", "贵州茅台"]),
    ("林知微", "同意库存是核心矛盾。我这边几个经销商反馈，腰部品牌比龙头更难走货。", "friends", ["白酒"]),
    ("林知微", "自己记下：茅台批价如果稳住，五粮液的批价弹性可能更大。先观察两周。", "self", ["贵州茅台", "五粮液"]),
    ("顾清越", "先进制程产能还是紧的，成熟制程价格战还没结束。设备材料要比晶圆厂本身更好跟踪。", "public", ["半导体", "中芯国际"]),
    ("沈予安", "本周问了几家封测，稼动环比持平，消费电子拉货还没起来。", "public", ["半导体", "消费电子"]),
    ("陆景行", "储能招标价格还在磨，但项目落地数量在增加。量在前、价在后，别被均价带偏节奏。", "public", ["储能", "宁德时代"]),
    ("叶晚宁", "电车周度批发还行，零售一般。渠道库存要盯紧，别把批发当真实需求。", "public", ["新能源车", "比亚迪"]),
    ("韩北辰", "欧洲装机节奏比国内稳，组件出口结构比总量更重要。", "public", ["光伏", "隆基绿能"]),
    ("苏晚晴", "硅料价格如果再下台阶，一体化龙头的利润表会比专业化更难看一段时间。", "friends", ["光伏"]),
    ("方知夏", "CXO订单能见度在恢复，但产能释放后的价格压力还在。选标的要看客户结构。", "public", ["CXO", "药明康德"]),
    ("程予舟", "创新药谈判规则越来越可预期，关键还是临床数据能不能进指南。", "public", ["医药"]),
    ("裴昭", "广告预算向效果广告集中，品牌广告仍弱。腾讯的游戏与广告弹性要分开看。", "public", ["港股互联网", "腾讯控股"]),
    ("江澄", "本地生活竞争还在，补贴强度决定短期利润。长期看供给密度。", "public", ["美团", "互联网"]),
    ("白露", "净息差下行斜率比绝对水平更重要，地产风险出清的时间表才是定价锚。", "public", ["银行", "地产"]),
    ("吴栖迟", "啤酒吨价提升还在，但销量弹性取决于夜场和即饮场景。", "public", ["啤酒"]),
    ("郑北野", "车企价格战还没结束，电池厂更要看开工和库存，而不是只看装机。", "public", ["新能源车", "宁德时代"]),
    ("宋以宁", "调味品动销温和复苏，餐饮渠道比零售更快一点。", "public", ["调味品", "海天味业"]),
    ("任晚舟", "军工信息化订单向头部集中，中小配套更看单一客户占比。", "public", ["军工"]),
    ("何远山", "安卓库存去化接近尾声，但换机周期还没到共振。先看高端机。", "public", ["消费电子"]),
    ("尹南风", "管线估值别只看峰值销售，支付和竞争格局会把峰值砍掉一半。", "friends", ["医药"]),
]


def seed_if_empty():
    if User.query.count() > 0:
        return
    pw = generate_password_hash(DEMO_PASSWORD, method="pbkdf2:sha256")
    tag_by_name = {}
    for name in PRESET_INDUSTRIES:
        t = Tag(name=name, kind="industry", is_preset=True)
        db.session.add(t)
        db.session.flush()
        tag_by_name[name] = t
    for name in PRESET_STOCKS:
        t = Tag(name=name, kind="stock", is_preset=True)
        db.session.add(t)
        db.session.flush()
        tag_by_name[name] = t
    extra = {"保险": "industry", "创新药": "industry"}
    for name, kind in extra.items():
        t = Tag(name=name, kind=kind, is_preset=False)
        db.session.add(t)
        db.session.flush()
        tag_by_name[name] = t

    now = datetime.utcnow()
    users = {}
    for i, u in enumerate(USERS):
        user = User(
            nickname=u["nickname"],
            password_hash=pw,
            role=u["role"],
            years=u["years"],
            signature=u["sig"],
            last_active_at=now - timedelta(minutes=(0 if i < 8 else 20 + i * 7)),
            created_at=now - timedelta(days=20 - i),
        )
        db.session.add(user)
        db.session.flush()
        users[u["nickname"]] = user
        for tn in u["tags"]:
            tag = tag_by_name.get(tn)
            if not tag:
                kind = "stock" if tn in PRESET_STOCKS else "industry"
                tag = Tag(name=tn, kind=kind, is_preset=False)
                db.session.add(tag)
                db.session.flush()
                tag_by_name[tn] = tag
            db.session.add(UserTag(user_id=user.id, tag_id=tag.id))

    for a, b in FRIEND_PAIRS:
        ua, ub = users[a], users[b]
        low, high = pair_ids(ua.id, ub.id)
        db.session.add(Friendship(user_low_id=low, user_high_id=high, created_at=now - timedelta(days=8)))
        db.session.add(
            FriendRequest(
                from_user_id=ua.id,
                to_user_id=ub.id,
                greeting="一起聊聊近期的研究框架？",
                status="accepted",
                created_at=now - timedelta(days=9),
                responded_at=now - timedelta(days=8),
            )
        )

    # 一条待处理请求：吴栖迟 → 林知微，方便演示收件箱
    db.session.add(
        FriendRequest(
            from_user_id=users["吴栖迟"].id,
            to_user_id=users["林知微"].id,
            greeting="我也在看白酒，最近怎么看？",
            status="pending",
            created_at=now - timedelta(hours=2),
        )
    )
    db.session.add(
        FriendRequest(
            from_user_id=users["梁小满"].id,
            to_user_id=users["周衡"].id,
            greeting="想请教下三季度宴席恢复你怎么看？",
            status="pending",
            created_at=now - timedelta(hours=5),
        )
    )

    thought_objs = []
    for i, (nick, body, vis, tnames) in enumerate(THOUGHTS):
        th = Thought(
            author_id=users[nick].id,
            body=body,
            visibility=vis,
            created_at=now - timedelta(hours=2 + i * 5),
        )
        db.session.add(th)
        db.session.flush()
        thought_objs.append(th)
        for tn in tnames:
            tag = tag_by_name[tn]
            db.session.add(ThoughtTag(thought_id=th.id, tag_id=tag.id))

    # 点赞
    like_pairs = [
        (0, "林知微"), (0, "赵观澜"), (0, "梁小满"), (0, "吴栖迟"),
        (3, "沈予安"), (3, "谢听潮"), (3, "许清和"),
        (5, "叶晚宁"), (5, "曹见山"), (5, "苏晚晴"),
        (9, "程予舟"), (11, "江澄"), (13, "秦牧"),
    ]
    for idx, nick in like_pairs:
        db.session.add(Like(user_id=users[nick].id, thought_id=thought_objs[idx].id))

    comments = [
        (0, "林知微", "库存结构比总量更重要，名酒和腰部要拆开看。"),
        (0, "赵观澜", "宴席恢复如果能持续到中秋，批价才有支撑。"),
        (3, "沈予安", "设备材料的订单能见度确实比晶圆厂更早。"),
        (5, "叶晚宁", "国内大储和工商储要分开建模，价格弹性不一样。"),
        (9, "程予舟", "客户结构比产能利用率更能解释利润差异。"),
        (11, "江澄", "效果广告占比提升对利润率是双刃剑。"),
    ]
    for idx, nick, text in comments:
        db.session.add(
            Comment(
                thought_id=thought_objs[idx].id,
                author_id=users[nick].id,
                content=text,
                created_at=now - timedelta(hours=1),
            )
        )

    # 好友会话样例
    def add_chat(a, b, lines, tag_name=None, hours_ago=6):
        ua, ub = users[a], users[b]
        low, high = pair_ids(ua.id, ub.id)
        conv = Conversation(
            user_a_id=low,
            user_b_id=high,
            source_tag_id=tag_by_name[tag_name].id if tag_name else None,
            last_message_at=now - timedelta(hours=hours_ago - 1),
        )
        db.session.add(conv)
        db.session.flush()
        t0 = now - timedelta(hours=hours_ago)
        for i, (who, text) in enumerate(lines):
            db.session.add(
                Message(
                    conversation_id=conv.id,
                    sender_id=users[who].id,
                    content=text,
                    created_at=t0 + timedelta(minutes=i * 8),
                    is_read=True,
                )
            )

    add_chat(
        "林知微",
        "周衡",
        [
            ("林知微", "最近渠道库存你怎么看？"),
            ("周衡", "总量仍高，但名酒比腰部好一些。"),
            ("林知微", "批价这边还在磨，先观察中秋前两周。"),
        ],
        "白酒",
        4,
    )
    add_chat(
        "沈予安",
        "顾清越",
        [
            ("沈予安", "封测稼动你这边听到什么？"),
            ("顾清越", "环比持平，消费电子还没明显拉货。"),
        ],
        "半导体",
        10,
    )

    db.session.commit()


# ==========================================================
# 玻璃球点评与邀请码资产（独立于用户种子数据，可随时补齐）
# ==========================================================

BROKERAGES = [
    {"name": "华兴证券", "short": "华兴", "hue": 20, "intro": "虚构机构。综合研究实力较强，消费与电子覆盖齐全。",
     "teams": ["食品饮料组", "电子组", "电新组", "医药组"]},
    {"name": "中诚证券", "short": "中诚", "hue": 48, "intro": "虚构机构。宏观策略见长，周期与金融地产覆盖扎实。",
     "teams": ["宏观策略组", "食品饮料组", "银行地产组"]},
    {"name": "泰和证券", "short": "泰和", "hue": 96, "intro": "虚构机构。制造业研究有特色，电新与军工跟踪紧密。",
     "teams": ["电子组", "电新组", "军工组"]},
    {"name": "弘远证券", "short": "弘远", "hue": 150, "intro": "虚构机构。医药与互联网研究投入大，路演响应快。",
     "teams": ["医药组", "消费组", "互联网组"]},
    {"name": "嘉信研究", "short": "嘉信", "hue": 190, "intro": "虚构机构。新能源与策略配置研究为主。",
     "teams": ["电新组", "新能源车组", "策略组"]},
    {"name": "鼎新证券", "short": "鼎新", "hue": 230, "intro": "虚构机构。半导体产业链跟踪细，专家资源丰富。",
     "teams": ["电子组", "半导体组", "通信组"]},
    {"name": "睿信证券", "short": "睿信", "hue": 275, "intro": "虚构机构。必选消费与家电研究稳健。",
     "teams": ["食品饮料组", "农业组", "家电组"]},
    {"name": "长明证券", "short": "长明", "hue": 320, "intro": "虚构机构。医药与军工研究积累深。",
     "teams": ["医药组", "军工组", "电新组"]},
]

REVIEW_TEXTS = [
    "深度报告质量不错，数据颗粒度细，但路演排期偏紧，临时约不太上。",
    "首席对产业节奏把握准，观点敢说，不做骑墙派。",
    "服务响应快，晚上十点还能回消息，这点很加分。",
    "派点性价比一般，服务做得很满但研究的增量信息不多。",
    "模型拆得很细，会给到底层假设，方便我们自己改参数。",
    "调研资源不错，能约到产业链关键人物，这点很难得。",
    "报告偏乐观，风险提示写得比较模板化，需要自己打折看。",
    "对政策变化的反应速度快，第一时间出解读。",
    "团队稳定性一般，人换得比较勤，跟踪连续性受影响。",
    "财务模型扎实，但对估值的讨论偏少。",
    "沟通顺畅，观点有变化时主动同步，不是只发报告。",
    "覆盖面广但深度参差，首席本人和助理的产出差距明显。",
    "对渠道和终端的跟踪做得细，草根数据有价值。",
    "响应速度取决于是不是重点客户，这点比较现实。",
    "研究独立性还可以，不太受投行项目影响。",
    "报告结论清晰，但推演过程略粗糙，需要自己补逻辑。",
]


def ensure_assets():
    """补齐玻璃球点评数据与邀请码。可重复执行，已有数据则跳过。"""
    import random

    from codes import gen_invite_code
    from models import (
        Brokerage,
        Feedback,
        InviteCode,
        ResearchTeam,
        Review,
        ReviewVote,
        TeamRating,
    )

    # 1) 玻璃球点评：券商与团队
    if Brokerage.query.count() == 0:
        rng = random.Random(20260909)
        for b in BROKERAGES:
            broker = Brokerage(name=b["name"], short_name=b["short"], intro=b["intro"], hue=b["hue"])
            db.session.add(broker)
            db.session.flush()
            for tname in b["teams"]:
                db.session.add(
                    ResearchTeam(
                        brokerage_id=broker.id,
                        name=tname,
                        intro=f"{b['name']}{tname}，虚构团队，仅用于演示。",
                    )
                )
        db.session.commit()

    # 2) 买方用户给团队打分（1-5 星）
    if TeamRating.query.count() == 0:
        rng = random.Random(4242)
        buyers = User.query.filter_by(role="buyer").all()
        teams = ResearchTeam.query.all()
        if buyers and teams:
            for team in teams:
                # 每个团队 3-6 位买方打分
                n = min(len(buyers), rng.randint(3, 6))
                for u in rng.sample(buyers, n):
                    base = rng.uniform(2.6, 4.9)
                    db.session.add(
                        TeamRating(
                            team_id=team.id,
                            user_id=u.id,
                            research=max(1, min(5, round(base + rng.uniform(-0.4, 0.5)))),
                            service=max(1, min(5, round(base + rng.uniform(-0.7, 0.6)))),
                            capital=max(1, min(5, round(base + rng.uniform(-1.0, 0.8)))),
                        )
                    )
            db.session.commit()

    # 3) 匿名评价
    if Review.query.count() == 0:
        rng = random.Random(777)
        buyers = User.query.filter_by(role="buyer").all()
        all_users = User.query.all()
        brokerages = Brokerage.query.all()
        teams = ResearchTeam.query.all()
        texts = list(REVIEW_TEXTS)
        rng.shuffle(texts)
        idx = 0
        # 券商评价：每家 1-2 条
        for b in brokerages:
            for _ in range(rng.randint(1, 2)):
                author = rng.choice(buyers) if buyers else None
                if not author:
                    break
                rec = Review(
                    target_type="brokerage",
                    target_id=b.id,
                    author_id=author.id,
                    content=texts[idx % len(texts)],
                )
                idx += 1
                db.session.add(rec)
        # 团队评价：每个团队 0-2 条
        for t in teams:
            for _ in range(rng.randint(0, 2)):
                author = rng.choice(buyers) if buyers else None
                if not author:
                    break
                rec = Review(
                    target_type="team",
                    target_id=t.id,
                    author_id=author.id,
                    content=texts[idx % len(texts)],
                )
                idx += 1
                db.session.add(rec)
        db.session.commit()

        # 给部分评价随机点赞 / 点踩
        reviews = Review.query.all()
        for r in reviews:
            for u in rng.sample(all_users, min(len(all_users), rng.randint(1, 5))):
                if u.id == r.author_id:
                    continue
                db.session.add(
                    ReviewVote(review_id=r.id, user_id=u.id, value=1 if rng.random() < 0.75 else -1)
                )
        db.session.commit()

    # 4) 邀请码：系统初始码 + 给没有码的用户补一张
    if InviteCode.query.count() == 0:
        for i in range(5):
            db.session.add(
                InviteCode(
                    code=gen_invite_code(exists=lambda c: InviteCode.query.filter_by(code=c).first()),
                    owner_user_id=None,
                    max_uses=5,
                    note="系统初始邀请码",
                )
            )
        db.session.commit()

    for u in User.query.all():
        if not InviteCode.query.filter_by(owner_user_id=u.id).first():
            db.session.add(
                InviteCode(
                    code=gen_invite_code(exists=lambda c: InviteCode.query.filter_by(code=c).first()),
                    owner_user_id=u.id,
                    max_uses=5,
                )
            )
    db.session.commit()

    # 5) 两条示例反馈
    if Feedback.query.count() == 0:
        demo_user = User.query.filter_by(nickname="林知微").first()
        if demo_user:
            db.session.add(Feedback(user_id=demo_user.id, content="希望随想能支持图片，看观点更直观。", status="open"))
            db.session.add(Feedback(user_id=demo_user.id, content="话题搜索能不能支持拼音首字母？打字慢。", status="resolved", admin_note="已记录，后续版本评估。"))
            db.session.commit()
