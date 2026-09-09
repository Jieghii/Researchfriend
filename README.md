# 研友 Demo

行业研究 & 股票交流社区演示站点。

**本项目为演示用途，不做真实身份认证，不得用于生产环境。请勿填写真实个人信息与真实密码。**

全站不接入任何真实行情。热度、涨跌、重合度均为站内计算或预置数据。

## 本地运行

需要 Python 3.11+。

```bash
cd code
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows；其他系统用 cp .env.example .env
python app.py
```

浏览器打开 http://127.0.0.1:5000

也可：`set FLASK_APP=app.py` 后执行 `flask run`。

未设置 `DATABASE_URL` 时使用项目目录下的 SQLite 文件 `yantou.db`。首次启动会自动建表并写入 28 个预置用户。

### 演示账号

预置用户密码统一为 `circle123`。例如：

- 买方：`林知微`
- 卖方：`周衡`

新昵称 + 密码会自动注册，并进入三步资料引导。

## 环境变量

| 变量 | 说明 |
|---|---|
| `SECRET_KEY` | 会话 Cookie 签名密钥，本地写在 `.env` |
| `DATABASE_URL` | 云端 Neon Postgres 连接串。本地不要设置，走 SQLite |
| `PORT` | 本地默认 5000；Zeabur 会自动注入 |

`.env` 已加入 `.gitignore`，不要提交到 Git。

## 部署到 Zeabur（推荐，国内直连无需翻墙）

`*.zeabur.app` 域名在大陆可直接访问，比 Vercel 默认域名稳定。仓库里已经放了 `Procfile` 与 `zbpack.json`，Zeabur 会自动识别为 Flask + Gunicorn。

1. 在 [Neon](https://neon.tech) 准备好 Postgres 数据库，复制连接串（需含 `sslmode=require`，应用会自动补上）。
2. 用 GitHub 账号登录 [zeabur.com](https://zeabur.com)。
3. 控制台点 **New Project** → 选个区域（**香港**或**新加坡**延迟最低）→ 进项目后 **Deploy from GitHub** → 选择 `Jieghii/Researchfriend` 这个仓库，**Branches to deploy** 选 `main`，点 Deploy，等待构建。
4. 进入刚部署好的服务 → **Variables**，新增：
   - `SECRET_KEY`：一段随机长字符串（可 `python -c "import secrets;print(secrets.token_hex(32))"` 生成）
   - `DATABASE_URL`：Neon 的 Postgres 连接串
   - `ADMIN_PASSWORD`：管理后台密码，建议改
   - （可选）`MAIL_SERVER` / `MAIL_PORT` / `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_FROM` / `MAIL_USE_SSL`：填齐后找回密码会真发邮件
5. 在 **Networking** 里点 **Generate Domain**，拿到一个 `*.zeabur.app` 域名，立即可访问，国内直连。
6. 后续 push 到 `main` 分支会自动重部署。

> Zeabur 免费 Starter 每月 $5 compute credits，Demo 跑这个 Flask 项目每月消耗大概 $1 以内；额度用完只暂停服务不删数据。

## 部署到 Vercel（旧）

> Vercel 的 `*.vercel.app` 域名在大陆被 DNS 污染，国内访问必须走 VPN。**新部署优先用 Zeabur**；如果仍需要走 Vercel 流程可参考下方。

1. 把本仓库推到 GitHub。
2. 在 [Neon](https://neon.tech) 创建 Postgres，复制连接串（需含 `sslmode=require`，应用会在缺失时自动补上）。
3. 在 Vercel 导入该仓库。
4. 在 Project → Settings → Environment Variables 配置：
   - `SECRET_KEY`：随机长字符串
   - `DATABASE_URL`：Neon 连接串
5. Deploy。`vercel.json` 已把全部路径转发到 `app.py` 中的 Flask 应用对象 `app`。

Vercel 无持久磁盘，**云端必须使用 Neon，不要用 SQLite**。

## 技术栈

Flask + SQLAlchemy + Jinja2 + 原生 CSS/JS。聊天每 3 秒轮询增量消息，心跳每 60 秒上报。

---

## 功能结构

| 板块 | 说明 |
|---|---|
| 加好友 | 翻咔式匹配卡片，按兴趣重合度推荐，打招呼 → 好友请求 → 同意 |
| 发现 | 话题（二级入口）、通讯录、玻璃球点评、用户反馈、邀请码 |
| 聊天 | 临时会话与好友会话，3 秒轮询 |
| 随想 | 朋友圈式短内容，三档可见范围，点赞评论 |
| 我的 | 个人资料、兴趣标签、随想、小统计 |

### 玻璃球点评规则
- 评分维度：研究能力 / 服务能力 / 钞能力，各 1-5 星
- **只有买方用户可以打分和评价**；卖方点击会提示「仅买方用户可以评价」
- 评价匿名展示，其他用户可点赞 / 点踩
- 券商得分 = 其下属团队得分的平均值，**用户不能直接给券商打分**
- 页面内所有券商与团队均为虚构，评分与评价均为演示用虚拟数据

### 账号体系
- 注册需要：昵称、密码、确认密码、邮箱（选填）、**邀请码（必填）**
- 未注册的昵称登录时不会被自动创建，会提示去注册
- 忘记密码：填昵称或邮箱 → 拿到重置链接（2 小时有效）→ 设置新密码
- 每位用户注册后自动获得自己的邀请码，额度 5 人
- 管理员可在 `/admin` 生成系统邀请码

### 管理后台
- 入口：`/admin`，密码来自环境变量 `ADMIN_PASSWORD`
- 功能：总览统计、用户管理（搜索 / 封禁 / 删除）、反馈处理、邀请码生成与停用

## 环境变量（Zeabur / Vercel）

| 变量 | 必填 | 说明 |
|---|---|---|
| `SECRET_KEY` | ✅ | 会话签名密钥 |
| `DATABASE_URL` | ✅ | Neon 连接串 |
| `ADMIN_PASSWORD` | ⚠️ 强烈建议 | 管理后台密码，不填则用默认密码（后台会提示风险） |
| `MAIL_SERVER` / `MAIL_PORT` / `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_FROM` / `MAIL_USE_SSL` | 可选 | 填齐后密码重置链接会真的发到邮箱；否则走演示模式（链接直接显示在页面上） |
| `INVITE_MAX_USES` | 可选 | 邀请码额度，默认 5 |

## 关于邮件（找回密码）

未配置邮件服务时，站点的找回密码走**演示模式**：申请后重置链接会直接显示在页面上，整个流程依然完整可用。

如需真的发邮件，以 QQ 邮箱为例：
1. 登录 QQ 邮箱网页版 → 设置 → 账号 → 开启 **IMAP/SMTP 服务**
2. 按提示生成**授权码**（不是你的 QQ 登录密码）
3. 在 Zeabur（Vercel 同理）环境变量里填：`MAIL_SERVER=smtp.qq.com`、`MAIL_PORT=465`、`MAIL_USERNAME=你的QQ邮箱`、`MAIL_PASSWORD=授权码`、`MAIL_FROM=你的QQ邮箱`、`MAIL_USE_SSL=1`

代码不需要任何改动。
