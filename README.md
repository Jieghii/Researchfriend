# 研投圈 Demo

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
| `PORT` | 本地默认 5000；Vercel 会自动注入 |

`.env` 已加入 `.gitignore`，不要提交到 Git。

## 部署到 Vercel

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
