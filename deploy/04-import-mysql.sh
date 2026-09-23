#!/usr/bin/env bash
# ============================================================
# 04 导入数据库（本机 mysqldump --databases recsys 导出后 scp 到服务器）
#   幂等：重复执行安全（先 DROP 再导入）
#   用法：bash 04-import-mysql.sh [/opt/recsys/recsys_dump.sql]
# ============================================================
set -euo pipefail

DUMP="${1:-/opt/recsys/recsys_dump.sql}"

if [ ! -f "$DUMP" ]; then
  echo "❌ 未找到数据库文件：$DUMP"
  echo "   请在本机执行并上传："
  echo "   mysqldump -uroot -proot --databases recsys > recsys_dump.sql"
  echo "   scp recsys_dump.sql root@<IP>:/opt/recsys/"
  exit 1
fi

echo "== 导入 $DUMP =="
mysql -uroot -proot --default-character-set=utf8mb4 < "$DUMP"

echo "== 校验 =="
mysql -uroot -proot -N -e \
  "SELECT CONCAT('book=',(SELECT COUNT(*) FROM recsys.book),' course=',(SELECT COUNT(*) FROM recsys.course),' movie=',(SELECT COUNT(*) FROM recsys.movie));"

echo ""
echo "✅ 数据库导入完成。"
echo "   浏览器访问 http://<服务器公网IP> 即可开启系统。"