# 部署工程设计说明

> 对应物料：`deploy/setup.sh`、`deploy/deploy.sh`、`deploy/workshop-qa.service`、`deploy/nginx.conf`、`deploy/README.md`
> 答辩可讲清的一句话：**前端构建产物由 FastAPI 直接托管，整站只有一个 8000 端口；Nginx 只负责 80/443 反代和「关闭缓冲」保证 SSE 真正流式；systemd 守护后端，密钥只放在 `backend/.env`（600 权限，不入库）。**

## 1. 部署形态

```
浏览器
  │  HTTP/HTTPS :80/:443
  ▼
Nginx ──反代，proxy_buffering off ──► FastAPI 127.0.0.1:8000
                                        ├─ 静态前端 frontend/dist
                                        ├─ Chroma data/chroma
                                        ├─ Ollama 127.0.0.1:11434（Qwen2.5 + bge-m3）
                                        └─ DeepSeek API（可选，云端兜底）
```

### 为什么不把前端交给 Nginx 静态托管

- 单端口部署，少一处 `root`/`try_files` 配置，也少一类「刷新 404」问题；
- 前端与 API 同源，没有 CORS；
- Nginx 只做两件事：TLS 终止和关缓冲，配置面小、出错概率低。

代价是 FastAPI 要读静态文件，但这部分开销可以忽略。

## 2. 本地运行（开发与演示）

```bash
# 1) Ollama（模型已拉取）
ollama serve
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull bge-m3

# 2) 后端
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Linux: .venv/bin/pip
cp .env.example .env                               # 填 DEEPSEEK_API_KEY（可选）
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3) 前端开发
cd frontend
npm ci
npm run dev        # Vite 代理 /api、/health 到 8000

# 4) 生产态本地验证（单端口）
cd frontend && npm run build
cd ../backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000
# 打开 http://127.0.0.1:8000/
```

首次导入知识库：

```bash
curl -X POST http://127.0.0.1:8000/api/kb/import
curl http://127.0.0.1:8000/api/kb/documents
```

## 3. 配置项

全部从 `backend/.env` 读取，`app/config.py` 集中管理；仓库只提交 `.env.example`。

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 地址 |
| `LLM_MODEL` | `qwen2.5:7b-instruct-q4_K_M` | 本地生成模型 |
| `EMBED_MODEL` | `bge-m3` | 向量模型 |
| `LLM_NUM_CTX` | `4096` | 上下文长度 |
| `RETRIEVAL_TOP_K` | `4` | 检索片段数 |
| `RETRIEVAL_MIN_SIM` | `0.6` | 拒答阈值（30 条问句校准） |
| `ROUTE_MODE` | `auto` | `auto` 允许云端兜底；`kb_only` 严格本地 |
| `DEEPSEEK_API_KEY` | 空 | 不填则云端不可用，界面显示「云端未配置」 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容端点 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 云端模型 |
| `CLOUD_TIMEOUT` | `60` | 云端超时秒数 |
| `CHROMA_DIR` / `DOCS_DIR` / `REGISTRY_PATH` | `data/...` | 相对路径按仓库根目录解析 |

安全约定：`.env` 权限 `600`、属主 `workshop`；`.gitignore` 排除；`setup.sh` 只在文件不存在时从示例复制，不会覆盖已有密钥。

## 4. 生产部署（Ubuntu 22.04/24.04）

### 4.1 一键初始化

```bash
sudo bash deploy/setup.sh
```

脚本按顺序做：

1. 检查 root、检查 `/opt/workshop-qa` 是否存在；
2. `apt` 安装 Python、venv、Nginx、Git 等；
3. Node < 18 时安装 Node 20；
4. 创建系统用户 `workshop`（无登录 shell）；
5. `chown -R workshop:workshop /opt/workshop-qa`；
6. `backend/.env` 不存在则从 `.env.example` 复制并 `chmod 600`；
7. 建 venv、装 `requirements.txt`；
8. `npm ci && npm run build`，把 `dist` 属主改为 `workshop`；
9. 安装 systemd 单元与 Nginx 站点，`nginx -t` 后 reload；
10. 打印 Ollama 安装与拉模型的后续命令。

脚本只做幂等操作，可重复执行；不会删除数据目录。

### 4.2 systemd

`deploy/workshop-qa.service`：

```ini
User=workshop
WorkingDirectory=/opt/workshop-qa/backend
ExecStart=/opt/workshop-qa/backend/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers
Restart=always
```

- `--workers 1`：诊断会话在进程内存，多 worker 会导致会话落到不同进程；扩容前先把会话迁到 Redis。
- `--proxy-headers`：让 FastAPI 识别 Nginx 转发的真实 IP/协议。
- 只监听 `127.0.0.1`，外网必须经 Nginx，避免绕过 TLS 和限流。

### 4.3 Nginx 与 SSE

关键三行：

```nginx
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 300s;
add_header X-Accel-Buffering no;
```

Nginx 默认会把上游响应攒够 buffer 再发，SSE 会变成「最后一次性返回」，演示时完全看不出流式。关闭缓冲后 `meta/delta/done` 才能逐条到达浏览器。`client_max_body_size 20m` 支持上传手册；`/health` 关闭 access log，避免监控刷日志。

### 4.4 HTTPS

有域名时：

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d <DOMAIN> --redirect
```

国内服务器 80/443 通常需要域名备案；没有域名可先用 IP + HTTP 演示，答辩前再决定是否上 HTTPS。

## 5. 日常更新

```bash
cd /opt/workshop-qa
sudo bash deploy/deploy.sh
```

流程：`git pull --ff-only` → `pip install -r requirements.txt` → `npm ci && npm run build` → `chown dist` → `systemctl restart workshop-qa` → `curl /health` 自检。任一步失败脚本退出，不会带着半成品重启。

## 6. 验收与自测

已在本地以「生产态」验证（FastAPI 单端口托管 dist）：

| 项 | 结果 |
| --- | --- |
| `/health` | `frontend_built=true`，`retrieval_min_sim=0.6`，`cloud_configured=true` |
| 首页 | 返回前端 HTML |
| 问答 | SSE 逐条 `meta → delta → done`，首字约 1 s |
| 云端升级 | `route` 事件出现，`model=deepseek-chat` |
| 诊断 | 完整链路 + A4 PDF 导出 |
| 知识库 | 导入、检索、删除正常 |

服务器到手后的公网自测清单在 `deploy/README.md` 第 1.6 节：健康检查、首页 HTML、`curl -N` 观察 SSE、外网访问四项。

## 7. 安全清单

- [x] 密钥只在 `backend/.env`，仓库只有 `.env.example`
- [x] `.env` 600、属主 `workshop`
- [x] 后端只监听 127.0.0.1
- [x] 上传只接受 `.md/.txt`，文件名去路径防穿越
- [x] 删除文档移入 `.trash` 而非直接删除
- [x] 诊断会话 2 小时 TTL，定期清理
- [ ] 公网访问鉴权（当前为演示开放，正式给工厂用需要加登录/白名单）
- [ ] 速率限制（可在 Nginx 加 `limit_req`）

## 8. 待用户提供的服务器信息

- [ ] 公网 IP
- [ ] SSH 端口与登录方式（密码/密钥，不要写进仓库）
- [ ] 是否有域名、是否已备案
- [ ] CPU/内存/是否有 GPU（决定 7B 还是 3B/4B 模型）
- [ ] 安全组是否放行 80/443

拿到后执行第 4 节，在外网完成第 6 节四项自测，并把结果补进 `docs/acceptance.md`。

## 9. 取舍与后续

| 选择 | 取舍 |
| --- | --- |
| FastAPI 托管前端 | 单端口、同源、配置少；静态资源性能不如 Nginx，但本项目规模足够 |
| 单 worker | 会话简单可靠；无法水平扩展，扩容需 Redis |
| 内存会话 | 零依赖；重启丢失，已在文档和界面提示 |
| 脚本部署而非 Docker | 比赛服务器环境简单、排查直观；Docker 化可作为后续增强 |
| 明文 HTTP 起步 | 无域名/备案时先跑通；有域名立刻上 certbot |

## 10. 答辩可能被问到的问题

- **为什么 SSE 要关 Nginx 缓冲？** 默认缓冲会把流攒起来一次性下发，用户看到的是「转圈很久 → 整段答案」；关掉后才有逐字效果。配置里同时加了 `X-Accel-Buffering: no` 双保险。
- **为什么只开一个 worker？** 诊断会话存在进程内存，多 worker 下第二次请求可能落到另一个进程，会话就丢了。要扩容先把会话迁到 Redis。
- **密钥怎么保证不进仓库？** `.gitignore` 排除 `backend/.env`，仓库只有 `.env.example`；部署脚本复制示例后 `chmod 600`；代码里只从环境变量读，不写默认密钥。
- **服务器配置不够怎么办？** 7B q4 约 4.7 GB，4 GB 内存的机器可换 `qwen2.5:3b-instruct-q4_K_M`，改 `LLM_MODEL` 即可，检索和前端不变；代价是回答质量略降。
- **断网还能用吗？** 本地路径完全不依赖外网；只有 `auto` 模式下的低置信问题会尝试云端，失败会回退为拒答并提示，不影响本地问答。
