#!/usr/bin/env bash
# 车间智答 —— 服务器更新脚本
# 用法（服务器上，仓库目录内）：sudo bash deploy/deploy.sh
# 作用：拉取最新代码 → 更新后端依赖 → 重新构建前端 → 重启服务 → 健康检查
set -euo pipefail

APP_DIR="/opt/workshop-qa"
APP_USER="workshop"

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 sudo 执行：sudo bash deploy/deploy.sh" >&2
  exit 1
fi

cd "${APP_DIR}"

echo "==> 拉取代码"
sudo -u "${APP_USER}" git pull --ff-only

echo "==> 更新后端依赖"
sudo -u "${APP_USER}" "${APP_DIR}/backend/.venv/bin/pip" install -r "${APP_DIR}/backend/requirements.txt"

echo "==> 构建前端"
cd "${APP_DIR}/frontend"
sudo -u "${APP_USER}" npm ci
sudo -u "${APP_USER}" npm run build
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}/frontend/dist"

echo "==> 重启服务"
systemctl restart workshop-qa
sleep 2

echo "==> 健康检查"
curl -fsS http://127.0.0.1:8000/health
echo
echo "更新完成。SSE 自测：curl -N -X POST http://127.0.0.1:8000/api/chat/stream -H 'Content-Type: application/json' -d '{\"query\":\"注塑机开机前需要检查什么\"}'"
