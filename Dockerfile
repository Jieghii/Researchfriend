FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=5000

WORKDIR /app

# 仅安装 psycopg2 编译需要的最小依赖（用 psycopg2-binary 时其实不需要，这里注释）
# RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# 暴露端口（云平台会自动注入 PORT 环境变量覆盖）
EXPOSE 5000

# 健康检查：访问 / 看是否 302 重定向到 /login（=应用启动成功）
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/login', timeout=3).read()"

# 默认入口：gunicorn 跑生产环境；本地开发可覆写为 python app.py
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers ${GUNICORN_WORKERS:-2} --timeout 120 --access-logfile - --error-logfile -"]
