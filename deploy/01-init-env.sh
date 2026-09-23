#!/usr/bin/env bash
# ============================================================
# 01 环境准备：JDK21 / Node18 / Python venv / MySQL / Redis / Nginx
# 适用：Ubuntu 24.04 LTS（root 执行）
#   bash 01-init-env.sh
# ============================================================
set -euo pipefail

echo "== [1/6] 系统更新与基础软件 =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y openjdk-21-jdk-headless maven python3-venv python3-pip \
    nodejs npm redis-server nginx git curl

echo "== [2/6] Python 虚拟环境（算法服务依赖） =="
python3 -m venv /opt/recsys/venv
/opt/recsys/venv/bin/pip install --upgrade pip -q
if [ -f /opt/recsys/recommender/requirements.txt ]; then
  /opt/recsys/venv/bin/pip install -r /opt/recsys/recommender/requirements.txt -q
  echo "    已安装 recommender/requirements.txt 依赖"
else
  echo "    [警告] 未找到 requirements.txt，请手动补齐算法服务依赖"
fi

echo "== [3/6] MySQL 8 安装与初始化 =="
apt-get install -y mysql-server
systemctl enable --now mysql
mysql -uroot <<'SQL'
ALTER USER 'root'@'localhost' IDENTIFIED WITH caching_sha2_password BY 'root';
CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED WITH caching_sha2_password BY 'root';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;
FLUSH PRIVILEGES;
SQL
echo "    MySQL root/root 已就绪（仅本机访问）"

echo "== [4/6] Redis =="
systemctl enable --now redis-server

echo "== [5/6] Nginx（HTTP 反代到 8080） =="
install -m 644 /opt/recsys/deploy/nginx-recserver.conf /etc/nginx/sites-available/recserver
ln -sf /etc/nginx/sites-available/recserver /etc/nginx/sites-enabled/recserver
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl enable --now nginx

echo "== [6/6] 防火墙（云安全组请另行放行 80） =="
if command -v ufw >/dev/null 2>&1; then ufw allow 80/tcp >/dev/null 2>&1 || true; fi

echo ""
echo "✅ 环境准备完成。下一步：bash 02-build.sh"