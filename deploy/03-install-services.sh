#!/usr/bin/env bash
# ============================================================
# 03 注册 systemd 服务：算法服务(8001) + 业务后端(8080)
#   幂等：重复执行会覆盖单元文件并 daemon-reload
#   bash 03-install-services.sh
# ============================================================
set -euo pipefail

cat > /etc/systemd/system/recsys-algo.service <<EOF
[Unit]
Description=RecSys Algo Service (FastAPI :8001)
After=network.target redis-server.service

[Service]
Type=simple
WorkingDirectory=/opt/recsys/recommender
ExecStart=/opt/recsys/venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/recsys-backend.service <<EOF
[Unit]
Description=RecSys Backend (SpringBoot :8080)
After=network.target mysql.service recsys-algo.service

[Service]
Type=simple
WorkingDirectory=/opt/recsys/backend
ExecStart=/usr/bin/java -jar target/recsys-backend-1.0.0.jar
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now recsys-algo recsys-backend

sleep 5
echo "== 服务状态 =="
systemctl is-active recsys-algo recsys-backend

echo ""
echo "✅ 服务已注册并启动。下一步：bash 04-import-mysql.sh"
echo "  查看日志：journalctl -u recsys-backend -f / journalctl -u recsys-algo -f"