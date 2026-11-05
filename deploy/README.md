# 部署说明（Deployment）

本目录是「车间智答」的 Linux 生产部署物料。目标环境：**Ubuntu 22.04 / 24.04，2 核 4 GB 以上，能访问 Ollama 模型仓库**。

## 0. 部署形态

```
浏览器
  │  HTTP/HTTPS :80/:443
  ▼
Nginx  ──反向代理（关闭缓冲，保证 SSE 流式）──►  FastAPI 127.0.0.1:8000
                                                   │
                                                   ├── Chroma 本地持久化（data/chroma）
                                                   ├── Ollama 127.0.0.1:11434（Qwen2.5 + bge-m3）
                                                   └── DeepSeek API（可选，云端兜底）
```

- 前端 `npm run build` 后由 FastAPI 直接托管 `frontend/dist`，**单端口即可完整运行**，减少 Nginx 静态路径配置。
- 诊断会话保存在进程内存，systemd 单元固定 `--workers 1`；若要多副本，需先把会话迁移到 Redis。
- `backend/.env` 是唯一密钥来源，权限 `600`，不进 Git。

## 1. 首次部署

### 1.1 准备服务器与代码

```bash
# 以 root 登录服务器
apt-get update && apt-get install -y git
git clone https://github.com/rqy18723992791-afk/workshop-qa.git /opt/workshop-qa
cd /opt/workshop-qa

# 填服务器信息（部署时替换）
# 公网 IP：<SERVER_IP>
# 域名：<DOMAIN>（可选，没有域名可先用 IP 访问）
```

### 1.2 一键初始化

```bash
sudo bash deploy/setup.sh
```

脚本会：安装 Python/Node/Nginx → 创建 `workshop` 运行用户 → 建虚拟环境装依赖 → `npm ci && npm run build` → 安装 systemd 服务与 Nginx 配置。首次运行若 `backend/.env` 不存在，会从 `.env.example` 复制一份，**记得填入 `DEEPSEEK_API_KEY`**。

### 1.3 安装 Ollama 与模型

```bash
curl -fsSL https://ollama.com/install.sh | sh
systemctl enable --now ollama

# 7B 量化模型约 4.7 GB，bge-m3 约 1.2 GB；显存不足可换 qwen2.5:3b-instruct-q4_K_M
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull bge-m3

# 验证
curl http://127.0.0.1:11434/api/tags
```

如果 Ollama 不在本机，修改 `backend/.env` 的 `OLLAMA_BASE_URL`，并确保网络可达。

### 1.4 填密钥并导入知识库

```bash
sudo nano /opt/workshop-qa/backend/.env
# DEEPSEEK_API_KEY=sk-...        ← 只填在这里，不要写进代码
# ROUTE_MODE=auto
# RETRIEVAL_MIN_SIM=0.6

sudo systemctl restart workshop-qa
curl -X POST http://127.0.0.1:8000/api/kb/import
curl http://127.0.0.1:8000/api/kb/documents
```

### 1.5 放行端口

云厂商安全组放行 **80**（以及 HTTPS 的 **443**）；如启用 ufw：

```bash
ufw allow 'Nginx Full'
ufw enable
```

### 1.6 公网自测清单

```bash
# 1) 健康检查：retrieval_min_sim=0.6，cloud_configured=true，frontend_built=true
curl -s http://127.0.0.1:8000/health | python3 -m json.tool

# 2) 首页返回前端 HTML（不是 JSON 提示）
curl -sI http://127.0.0.1:8000/ | head -5

# 3) SSE 流式：应逐条看到 meta / delta / done，而不是最后一次性返回
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"query":"注塑机开机前需要检查什么？"}'

# 4) 外网访问
curl -s http://<SERVER_IP>/health
```

浏览器打开 `http://<SERVER_IP>/`，依次演示：本地问答 → 故障排查向导 → 云端升级问题 → 知识库检索台。

## 2. HTTPS（有域名时建议）

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d <DOMAIN> --redirect
sudo certbot renew --dry-run
```

把 `deploy/nginx.conf` 中的 `server_name _;` 改成实际域名后重新安装配置：

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/workshop-qa
sudo nginx -t && sudo systemctl reload nginx
```

## 3. 日常更新

```bash
cd /opt/workshop-qa
sudo bash deploy/deploy.sh
```

脚本执行 `git pull --ff-only` → 更新依赖 → 重建前端 → `systemctl restart workshop-qa` → 健康检查。

## 4. 运维命令

| 操作 | 命令 |
| --- | --- |
| 查看服务状态 | `systemctl status workshop-qa` |
| 实时日志 | `journalctl -u workshop-qa -f` |
| 重启后端 | `systemctl restart workshop-qa` |
| 重载 Nginx | `nginx -t && systemctl reload nginx` |
| 查看 Ollama | `systemctl status ollama` / `journalctl -u ollama -f` |
| 重建向量索引 | `curl -X POST http://127.0.0.1:8000/api/kb/reindex` |

## 5. 常见问题

| 现象 | 排查 |
| --- | --- |
| 页面能开，提问报 502 | `journalctl -u workshop-qa -n 100`；确认 8000 端口有进程 |
| 问答一次性出现、没有流式 | Nginx 未关闭 `proxy_buffering`；检查是否用了 `deploy/nginx.conf` |
| `/health` 里 `cloud_configured=false` | `backend/.env` 没有 `DEEPSEEK_API_KEY`，或服务没重启 |
| 检索全部低于阈值 | 知识库未导入：`curl -X POST :8000/api/kb/import`；或 Ollama 的 bge-m3 未拉取 |
| 回答很慢 | 首次加载模型需 10–30 s；检查 GPU/CPU 占用，必要时换 4B/3B 量化模型 |
| 上传/删除文档失败 | `data/` 目录属主必须是 `workshop`：`chown -R workshop:workshop /opt/workshop-qa/data` |
| 诊断向导重启后会话丢失 | 设计如此（内存会话，2 小时 TTL）；生产多副本需 Redis |

## 6. 本地“生产态”全链路验证（已执行）

不依赖 Nginx，验证 FastAPI 单端口托管前端：

```bash
cd frontend && npm ci && npm run build
cd ../backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
# 浏览器打开 http://127.0.0.1:8000/
```

2026-11-05 本地实测：`/health` 返回 `frontend_built=true`；三个页面（问答/排查/知识库）可访问；SSE 本地与云端两条路径均通过；处置单可打印为 A4 PDF。证据见 `docs/acceptance.md`。

## 7. 待填服务器信息

部署到公网前需要用户提供：

- [ ] 服务器公网 IP
- [ ] SSH 端口与登录方式（不要把密码写进仓库）
- [ ] 是否有域名 / 是否已备案（国内服务器 80/443 可能需要备案）
- [ ] 服务器配置（CPU、内存、是否有 GPU）——决定用 7B 还是 4B/3B 模型
- [ ] 云厂商安全组是否已放行 80/443

拿到信息后执行第 1 节并在外网完成第 1.6 节自测。
