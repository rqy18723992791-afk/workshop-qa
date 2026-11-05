#!/usr/bin/env bash
# 车间智答 —— Ubuntu 22.04/24.04 一键初始化脚本
#
# 前提：
#   1. 仓库已克隆到 /opt/workshop-qa（如路径不同，同时修改本脚本与 systemd 单元）
#   2. 以 root 或有 sudo 的用户执行：sudo bash deploy/setup.sh
#
# 脚本做五件事：装系统依赖 → 建 Python 虚拟环境 → 构建前端 →
# 安装 systemd 服务 → 安装 Nginx 反代。Ollama 模型需单独拉取（脚本末尾提示）。
set -euo pipefail

APP_DIR="/opt/workshop-qa"
APP_USER="workshop"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 sudo 执行：sudo bash deploy/setup.sh" >&2
  exit 1
fi

if [[ ! -f "${APP_DIR}/backend/app/main.py" ]]; then
  echo "未找到 ${APP_DIR}/backend/app/main.py，请先把仓库克隆到 ${APP_DIR}" >&2
  exit 1
fi

echo "==> 1/5 安装系统依赖"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  python3 python3-venv python3-pip \
  nginx curl ca-certificates \
  nodejs npm git

# Ubuntu 自带的 nodejs 版本可能低于 Vite 6 要求（>=18），必要时用 NodeSource。
NODE_MAJOR="$(node --version 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/' || echo 0)"
if [[ "${NODE_MAJOR}" -lt 18 ]]; then
  echo "Node.js 版本过低（${NODE_MAJOR}），安装 Node.js 20 LTS"
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

echo "==> 2/5 创建运行用户与目录"
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "${APP_USER}"
fi
mkdir -p "${APP_DIR}/data/chroma" "${APP_DIR}/data/docs"
# 应用目录交给运行用户，后续 git pull / npm ci / 上传文档都不需要 root
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

if [[ ! -f "${APP_DIR}/backend/.env" ]]; then
  cp "${APP_DIR}/.env.example" "${APP_DIR}/backend/.env"
  echo "!! 已生成 backend/.env，请填入 DEEPSEEK_API_KEY 后重启服务（不填则云端兜底不可用）"
fi
chown "${APP_USER}:${APP_USER}" "${APP_DIR}/backend/.env"
chmod 600 "${APP_DIR}/backend/.env"

echo "==> 3/5 安装后端依赖并构建前端"
sudo -u "${APP_USER}" "${PYTHON_BIN}" -m venv "${APP_DIR}/backend/.venv"
sudo -u "${APP_USER}" "${APP_DIR}/backend/.venv/bin/pip" install --upgrade pip
sudo -u "${APP_USER}" "${APP_DIR}/backend/.venv/bin/pip" install -r "${APP_DIR}/backend/requirements.txt"

cd "${APP_DIR}/frontend"
sudo -u "${APP_USER}" npm ci
sudo -u "${APP_USER}" npm run build
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}/frontend/dist"

echo "==> 4/5 安装 systemd 服务"
install -m 644 "${APP_DIR}/deploy/workshop-qa.service" /etc/systemd/system/workshop-qa.service
systemctl daemon-reload
systemctl enable --now workshop-qa
systemctl restart workshop-qa

echo "==> 5/5 安装 Nginx 反向代理"
install -m 644 "${APP_DIR}/deploy/nginx.conf" /etc/nginx/sites-available/workshop-qa
ln -sf /etc/nginx/sites-available/workshop-qa /etc/nginx/sites-enabled/workshop-qa
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo
echo "基础部署完成。剩余手动步骤："
echo "  1) 安装并启动 Ollama：curl -fsSL https://ollama.com/install.sh | sh"
echo "  2) 拉取模型：ollama pull qwen2.5:7b-instruct-q4_K_M && ollama pull bge-m3"
echo "  3) 导入知识库：curl -X POST http://127.0.0.1:8000/api/kb/import"
echo "  4) 自测：curl http://127.0.0.1:8000/health"
echo "  5) 公网访问：http://<服务器公网IP>/（安全组/防火墙放行 80 端口）"
echo
echo "查看服务日志：journalctl -u workshop-qa -f"
