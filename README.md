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

## 部署到腾讯云 / 阿里云 / 任意 Linux 服务器（最稳，国内极速）

> 适合 100+ 用户长期运行，**不会冷启动、不休眠**、单实例能扛到 300 并发，5-10 元/月。

仓库自带 `Dockerfile` + `docker-compose.yml` + `deploy.sh` 一键脚本。任意 Ubuntu/Debian 服务器买好之后，SSH 上去跑一行命令即可。

### 准备

1. 买一台轻量服务器，配置推荐：
   - **腾讯云轻量应用服务器 2核2G**：年付 68 元（约 5.7 元/月），[购买链接](https://cloud.tencent.com/product/lighthouse)
   - 镜像选 **Ubuntu 22.04 LTS**，公网带宽 5 Mbps 就够
   - 安全组放通 22 / 80 / 443 / 5000 端口

2. 服务器绑 SSH，本地能连上。Windows 可用 PowerShell + OpenSSH 或 Termius。

### 一键部署

```bash
# 1. SSH 登录服务器
ssh root@你的服务器IP

# 2. 把代码传上去（三选一）
#    a. 直接从 GitHub 拉（推荐）
cd /opt
git clone https://github.com/Jieghii/Researchfriend.git researchfriend
cd researchfriend/code

#    b. 或者用 scp 从本机推上去
#       scp -r 本机项目路径/* root@你的IP:/opt/researchfriend/code/

# 3. 一键安装 + 启动
bash deploy.sh
```

`deploy.sh` 会自动做：
1. 检测/安装 Docker 和 docker compose
2. 生成 `SECRET_KEY`、`POSTGRES_PASSWORD`、`ADMIN_PASSWORD`（写入 `.env`）
3. `docker compose up -d --build` 构建并启动 Flask + Postgres 容器
4. 可选安装 Nginx 反向代理（用 80 端口访问，不用输 :5000）
5. 输出访问地址

### 后续维护

```bash
# 查看实时日志
cd /opt/researchfriend/code && docker compose logs -f web

# 更新代码后重部署
cd /opt/researchfriend/code && git pull && docker compose up -d --build

# 备份数据库
docker compose exec db pg_dump -U researchfriend researchfriend > backup_$(date +%F).sql

# 恢复数据库
cat backup_2026-01-01.sql | docker compose exec -T db psql -U researchfriend -d researchfriend
```

### 绑定域名 + HTTPS

买好域名解析到服务器 IP，然后：

```bash
# 安装 certbot 申请免费证书
apt install -y certbot python3-certbot-nginx
certbot --nginx -d yourdomain.com
```

Certbot 自动改 Nginx 配置加 HTTPS。

---

## 部署到 Zeabur（国内直连，Free plan 有冷启动限制）

`*.zeabur.app` 域名在大陆可直接访问。仓库里已经放了 `Procfile` 与 `zbpack.json`，Zeabur 会自动识别为 Flask + Gunicorn。

> ⚠️ **Free Plan 限制**：每月 $5 credit，1 vCPU / 2 GB，**闲置后会自动休眠（冷启动几秒）**。100 用户长期使用建议升级 Dev Plan（$5/月，不休眠）。

### Free Plan 操作步骤（不收钱，但有冷启动）

1. 用 GitHub 账号登录 [zeabur.com](https://zeabur.com)。**不要**点订阅付费套餐，没订阅就默认是 Free Plan。
2. 在 [Neon](https://neon.tech) 准备好 Postgres 数据库，复制连接串。
3. 控制台 → **Create Project** → 选区域（**香港** / **新加坡** / **东京** 这些亚洲节点是免费的，欧美节点要付费）。
4. 进项目 → **Add Service** → 选 **Deploy your source code (GitHub)** → 授权仓库 → 选 `Jieghii/Researchfriend` 的 `main` 分支 → 点 Deploy。
5. 等待 1-3 分钟构建完成。
6. 进入刚部署好的服务 → **Variables**，新增：
   - `SECRET_KEY`：随机长字符串（PowerShell 跑 `python -c "import secrets;print(secrets.token_hex(32))"` 生成）
   - `DATABASE_URL`：Neon 的 Postgres 连接串
   - `ADMIN_PASSWORD`：管理后台密码，建议改
7. 在 **Networking** → **Generate Domain** 拿一个 `*.zeabur.app` 域名，立即可访问，国内直连。
8. 后续 push 到 `main` 分支会自动重部署。

### 切换 Dev Plan（避免休眠）

控制台 → 右上角头像 → **Billing** → 选 **Dev Plan ($5/mo)** → 14 天免费试用，过后扣 $5/月。

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
