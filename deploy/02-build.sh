#!/usr/bin/env bash
# ============================================================
# 02 构建：前端（输出到后端 static） + 后端 jar
#   bash 02-build.sh
# ============================================================
set -euo pipefail

echo "== [1/2] 构建前端 =="
cd /opt/recsys/frontend
npm config set registry https://registry.npmmirror.com  # 国内镜像加速
npm install
npm run build      # vite 产物直接输出到 ../backend/src/main/resources/static

echo "== [2/2] 构建后端 jar =="
cd /opt/recsys/backend
mvn -q -DskipTests package
ls -lh target/recsys-backend-1.0.0.jar

echo ""
echo "✅ 构建完成。下一步：bash 03-install-services.sh"