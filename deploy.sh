#!/usr/bin/env bash
# 一键部署到任意 Ubuntu/Debian 服务器（腾讯云/阿里云/华为云/本地虚拟机通用）
# 用法：
#   1. 把整个项目目录（或 git clone 下来）上传到服务器
#   2. SSH 进去跑：bash deploy.sh
#   3. 按提示输入域名或公网 IP

set -e

# ---------- 颜色 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${BLUE}[INFO]${NC} $*"; }
ok() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err() { echo -e "${RED}[ERR]${NC} $*"; }

# ---------- 检测 ----------
if [ "$(id -u)" -ne 0 ]; then
  err "请用 root 跑：sudo bash deploy.sh"
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

info "项目目录：$PROJECT_DIR"

# ---------- 1. 安装 Docker ----------
if ! command -v docker >/dev/null 2>&1; then
  info "安装 Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
  ok "Docker 安装完成"
else
  ok "Docker 已安装：$(docker --version)"
fi

# ---------- 2. 安装 Docker Compose ----------
if ! docker compose version >/dev/null 2>&1; then
  info "安装 docker-compose 插件..."
  apt-get install -y docker-compose-plugin
fi
ok "docker compose 可用：$(docker compose version)"

# ---------- 3. 生成密钥 ----------
generate_secret() {
  python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null \
    || openssl rand -hex 32
}

# ---------- 4. 写 .env ----------
if [ ! -f .env ]; then
  info "生成 .env 配置文件..."
  POSTGRES_PW=$(generate_secret)
  SECRET=$(generate_secret)

  read -p "请输入域名或公网 IP（直接回车则用服务器 IP + 5000 端口）: " DOMAIN
  if [ -z "$DOMAIN" ]; then
    PUBLIC_HOST=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "localhost")
    DOMAIN="${PUBLIC_HOST}"
    USE_DOMAIN=0
  else
    USE_DOMAIN=1
  fi

  read -p "请输入管理后台密码（直接回车用 admin123，建议改）: " ADMIN_PW
  ADMIN_PW=${ADMIN_PW:-admin123}

  cat > .env <<EOF
# 自动生成于 $(date '+%Y-%m-%d %H:%M:%S')
POSTGRES_PASSWORD=$POSTGRES_PW
SECRET_KEY=$SECRET
ADMIN_PASSWORD=$ADMIN_PW
DOMAIN=$DOMAIN
USE_DOMAIN=$USE_DOMAIN
EOF
  ok ".env 已生成（请妥善保管）"
else
  info ".env 已存在，跳过生成"
  source .env
  DOMAIN=${DOMAIN:-localhost}
  USE_DOMAIN=${USE_DOMAIN:-0}
fi

# ---------- 5. 启动 ----------
info "构建并启动服务（首次会下载镜像，约 1-3 分钟）..."
docker compose up -d --build

# ---------- 6. 等服务起来 ----------
info "等待数据库就绪..."
for i in $(seq 1 30); do
  if docker compose exec -T db pg_isready -U researchfriend >/dev/null 2>&1; then
    ok "数据库就绪"
    break
  fi
  sleep 2
done

info "等待 Web 服务..."
for i in $(seq 1 30); do
  if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/login | grep -q "200"; then
    ok "Web 服务已启动"
    break
  fi
  warn "Web 还没好，等 2 秒再试（$i/30）"
  sleep 2
done

# ---------- 7. 防火墙 ----------
info "开放 5000 端口（如有 ufw）..."
if command -v ufw >/dev/null 2>&1; then
  ufw allow 5000/tcp 2>/dev/null || true
fi

# ---------- 8. 安装 Nginx 反向代理（可选）----------
read -p "是否安装 Nginx 反向代理（用 80/443 端口访问，不用输 :5000）? [Y/n] " INSTALL_NGINX
INSTALL_NGINX=${INSTALL_NGINX:-Y}

if [[ "$INSTALL_NGINX" =~ ^[Yy]$ ]]; then
  if ! command -v nginx >/dev/null 2>&1; then
    info "安装 Nginx..."
    apt-get install -y nginx
  fi

  cat > /etc/nginx/sites-available/researchfriend <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 20M;

    location /static/ {
        alias $PROJECT_DIR/static/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
EOF

  ln -sf /etc/nginx/sites-available/researchfriend /etc/nginx/sites-enabled/
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl reload nginx
  ok "Nginx 已配置"
fi

# ---------- 9. 输出 ----------
info "================================="
ok "部署完成！"
echo
echo "访问方式："
echo "  - 直接访问：http://$DOMAIN:5000"
if [[ "$INSTALL_NGINX" =~ ^[Yy]$ ]]; then
  echo "  - 经 Nginx：http://$DOMAIN"
fi
echo
echo "管理后台：http://$DOMAIN/admin"
echo "  密码：你的 ADMIN_PASSWORD"
echo
echo "查看日志："
echo "  docker compose logs -f web"
echo
echo "更新代码后重新部署："
echo "  git pull && docker compose up -d --build"
