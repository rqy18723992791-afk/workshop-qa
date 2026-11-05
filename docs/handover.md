# 交接文档 · 车间智答

> 更新时间：2026-11-05
> 适用对象：接手的队友、指导教师、后续维护者
> 仓库：<https://github.com/rqy18723992791-afk/workshop-qa>（公开，MIT）
> 当前状态：**八项交付全部完成初版并验收留痕；本地生产态可跑；公网部署、视频成片、平台提交待办。**

本文档只写“接手后立刻要知道的事”：怎么跑、东西在哪、哪些不能动、还差什么。设计原理看 [docs/index.md](index.md)，验收数据看 [acceptance.md](acceptance.md)。

---

## 1. 一句话说明项目

「车间智答」是面向注塑机车间的本地 RAG 知识问答 + 故障排查 Web 应用：设备手册、点检标准、故障案例入库后，工人用自然语言提问，系统用本机 Qwen2.5 流式作答并给出处；资料不足时明确拒答；低置信问题按配置升级 DeepSeek，界面标出“云端”及原因；温度异常等故障走确定性状态机，最后生成可打印的 A4 处置单。

**当前完成度**

| 范围 | 状态 |
| --- | --- |
| 问答、引用、拒答、端云路由 | ✅ 实测通过 |
| 故障诊断状态机 + 处置单导出 | ✅ 6 步完整链实测通过 |
| MCP 工具封装 | ✅ 官方客户端实测通过 |
| 工业风前端三视图 + 移动端 | ✅ 截图留痕 |
| 技术文档 PDF（25 页） | ✅ 仓库根目录 |
| 视频脚本（5–8 分钟） | ✅ 结构定稿，队伍信息占位 |
| README / LICENSE / 设计说明 / 验收记录 | ✅ 已入库 |
| 公网部署 | 🟡 物料齐备，等服务器信息 |
| 演示视频成片、平台报名提交 | ⬜ 用户侧 |

---

## 2. 关键链接与权限

| 事项 | 地址 / 说明 |
| --- | --- |
| 开源仓库 | <https://github.com/rqy18723992791-afk/workshop-qa> |
| 在线演示 | 待部署后补；计划无需登录 |
| 演示视频 | 待录制后补 |
| 技术文档 | 仓库根目录 `车间智答-技术文档.pdf` |
| 设计说明总索引 | [docs/index.md](index.md) |
| 逐项验收 | [docs/acceptance.md](acceptance.md) |
| 部署手册 | [deploy/README.md](../deploy/README.md) |

仓库为公开仓库，评审可直接克隆，无需账号或权限申请。推送权限在仓库所有者账号下，队友协作需所有者邀请；**任何密钥、服务器密码、平台账号都不要写进仓库或聊天记录**。

---

## 3. 五分钟跑起来（本机 Windows 开发环境）

### 3.1 前置

- Python 3.11+、Node.js 18+（推荐 20）
- Ollama，已拉取 `qwen2.5:7b-instruct-q4_K_M` 与 `bge-m3`
- DeepSeek Key 可选；不填则云端路由不可用，界面显示“云端未配置”

本机是便携版 Ollama，可执行文件在 `D:\tools\ollama\ollama.exe`，模型目录 `D:\tools\ollama-models`，未注册系统服务，**每次开机需手动启动**：

```bash
OLLAMA_MODELS="D:\tools\ollama-models" /d/tools/ollama/ollama.exe serve
```

### 3.2 配置

```bash
cd "D:\大学\竞赛\传智杯"
cp .env.example backend/.env
# 编辑 backend/.env，填 DEEPSEEK_API_KEY（可留空）
```

`backend/.env` 已被 `.gitignore` 排除，**永远不要提交**。

### 3.3 启动后端

```bash
cd "D:\大学\竞赛\传智杯\backend"
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

首次在新机器上：

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

健康检查：<http://127.0.0.1:8000/health>，应返回模型名、阈值 0.6、路由模式与 `frontend_built`。

### 3.4 启动前端

开发态（热更新，端口 5173，`/api` 已代理到 8000）：

```bash
cd "D:\大学\竞赛\传智杯\frontend"
npm ci
npm run dev
```

生产态（单端口，FastAPI 直接托管 `dist`）：

```bash
cd "D:\大学\竞赛\传智杯\frontend"
npm run build
# 然后只开 8000，访问 http://127.0.0.1:8000/
```

> 先 build 再启动后端；改了前端必须重新 build，否则 8000 端口还是旧页面。浏览器缓存顽固时按 `Ctrl+F5`。

### 3.5 首次导入知识库

```bash
curl -X POST http://127.0.0.1:8000/api/kb/import
curl http://127.0.0.1:8000/api/kb/documents
```

15 份文档、123 个切片，首次向量化约 10–30 秒。`data/chroma/` 与 `data/kb_registry.json` 是运行时数据，**不在仓库里**；新克隆的仓库必须导入一次。

### 3.6 五个演示动作

1. 问“注塑机开机前需要检查什么？”→ 本地答案 + 引用卡片；
2. 问“如何做红烧肉？”→ 明确拒答，来源为空；
3. 问“注塑机螺杆磨损到什么程度必须更换？”→ 本地拒答后自动切云端，标签变蓝；
4. 进“故障排查”→ 走完不加热链路 → 生成处置单 → 打印 / 下载 Markdown；
5. 进“知识库”→ 检索测试台，改问题看相似度与阈值。

---

## 4. 目录地图（接手先看这些）

| 路径 | 作用 | 备注 |
| --- | --- | --- |
| `backend/app/main.py` | FastAPI 入口、静态托管 `frontend/dist` | 生产单端口 |
| `backend/app/config.py` | 环境变量、路径、阈值 | 参数都从这里读 |
| `backend/app/routers/chat.py` | `/api/chat`、`/api/chat/stream` | SSE 协议 |
| `backend/app/routers/kb.py` | 导入、上传、删除、检索 | 管理接口 |
| `backend/app/routers/diag.py` | 诊断会话、报告 | 内存会话 |
| `backend/app/services/retrieval.py` | bge-m3 + Chroma 检索 | top-k、阈值 |
| `backend/app/services/generation.py` | 本地 Qwen 生成、两层拒答 | 提示词 |
| `backend/app/services/routing.py` | 端云决策、事件序列 | 拒答缓冲 |
| `backend/app/services/cloud.py` | DeepSeek 调用 | httpx |
| `backend/app/services/diagnosis.py` | 12 节点 / 11 结论状态机 | `_TOPICS` 数据 |
| `backend/mcp_server.py` | MCP stdio Server | 两个工具 |
| `frontend/src/components/ChatView.vue` | 问答主界面、SSE 消费 | 引用联动 |
| `frontend/src/components/DiagnosisView.vue` | 诊断向导、A4 打印 | 打印 CSS |
| `frontend/src/components/KnowledgeView.vue` | 知识库管理/检索台 | 上传、删除 |
| `frontend/src/style.css` | 工业风设计令牌 | 改主题先改这里 |
| `backend/scripts/calibrate.py` | 30 条阈值校准 | 可复现 |
| `backend/scripts/acceptance_routes.py` | 三路径 + 诊断验收 | 写 `docs/evidence/` |
| `deploy/` | `setup.sh` / `deploy.sh` / systemd / Nginx | 公网部署用 |
| `docs/` | 设计说明、验收、证据、脚本 | 答辩复习 |
| `data/docs/` | 15 份示例知识库 | 自编演示数据 |

---

## 5. 验收怎么复现

前提：Ollama 与后端均在运行，知识库已导入。

```bash
cd "D:\大学\竞赛\传智杯"

# 1) 30 条问句阈值校准（只检索不生成，约 1 分钟）
backend/.venv/Scripts/python.exe backend/scripts/calibrate.py

# 2) 本地/云端/拒答三路径 + 完整诊断链（会调用模型，约 2–3 分钟）
backend/.venv/Scripts/python.exe backend/scripts/acceptance_routes.py

# 3) MCP 官方客户端调用
backend/.venv/Scripts/python.exe backend/scripts/test_mcp_client.py
```

预期结果（2026-11-05 实测）：

| 项 | 结果 |
| --- | --- |
| 本地路径 | top-1 `0.7833`，`route=local`，`qwen2.5:7b`，引用 3 份文档 |
| 云端升级 | top-1 `0.6589`，本地拒答后 `route→cloud`，`deepseek-chat` |
| 拒答 | `0.4242 < 0.6`，`refused=true`，`sources=[]` |
| 诊断 | 6 步，结论 SSR 损坏，报告号 `CZ-20261105-070AF4` |
| MCP | `has_relevant=True`，`max_score=0.8078`，15 份文档 |

输出写入 `docs/evidence/`。每次改检索、提示词、路由后都应重跑并更新 [acceptance.md](acceptance.md)，不要把旧证据当新结果。

---

## 6. 关键参数（不要随手改）

| 参数 | 值 | 依据 |
| --- | --- | --- |
| 切片长度 / 重叠 | 600 字 / 80 字 | 中文手册段落完整性与上下文平衡 |
| 向量模型 | `bge-m3`，1024 维 | 中文检索效果 |
| 检索 top-k | 4 | 覆盖多文档又不过度稀释 |
| 拒答阈值 | **0.6** | 30 条问句校准的安全带中点 |
| 生成模型 | `qwen2.5:7b-instruct-q4_K_M` | 8 GB 显存可跑，中文稳定 |
| 路由模式 | `auto`（默认）/ `kb_only` | 低置信才上云 |
| 诊断会话 TTL | 2 小时，内存保存 | 重启即丢失，设计如此 |
| 处置单编号 | `CZ-YYYYMMDD-XXXXXX` | 按日期 + 随机后缀 |

阈值改动必须重新跑 `calibrate.py` 并更新校准记录；把 0.6 调低会放行无关问题，调高会误伤正常提问。

---

## 7. 已验收内容摘要

| 交付项 | 结论 | 证据入口 |
| --- | --- | --- |
| 前端问答界面 | ✅ SSE、引用卡片、三态路由标识、移动端 | `docs/assets/chat-*.png` |
| 拒答阈值校准 | ✅ 30 条问句，阈值 0.6 | [calibration.md](calibration.md) |
| 故障排查向导 | ✅ 6 步 + A4 处置单 + Markdown | [evidence/diagnosis-session.json](evidence/diagnosis-session.json) |
| 端云协同路由 | ✅ 三路径实测 | [route-local.json](evidence/route-local.json)、[route-cloud.json](evidence/route-cloud.json)、[route-refusal.json](evidence/route-refusal.json) |
| MCP 封装 | ✅ 官方客户端可调用 | [evidence/mcp-test.txt](evidence/mcp-test.txt) |
| 部署 | 🟡 本地生产态通过，公网待办 | [deployment.md](deployment.md) |
| 材料初稿 | ✅ PDF 25 页、视频脚本、README、LICENSE | 仓库根目录 |
| 设计说明 | ✅ 八页讲义式文档 | [index.md](index.md) |

---

## 8. 没做完的事与责任划分

| 事项 | 当前卡点 | 谁来做 | 接手步骤 |
| --- | --- | --- | --- |
| 公网部署 / 在线演示 | 缺服务器 IP、SSH、域名/备案、配置、安全组 | 用户提供信息，我执行 | 跑 `deploy/setup.sh` → 外网四项自测 → 把地址填进 README |
| 演示视频成片 | 需真人旁白、剪辑、队伍信息 | 用户 | 按 [video-script.md](video-script.md) 录 5–8 分钟、≥1080p |
| 团队/学校/指导教师信息 | 用户尚未提供 | 用户 | 替换脚本与 `docs/tech-doc.html` 中 `【】` 占位，再重出 PDF |
| 平台报名、缴费、最终提交 | 属账号与对外提交 | 用户 | 按大赛通知操作 |
| 在线演示加分项 | 依赖公网部署 | 部署后补 | 无需登录，准备演示数据与四段自测 |

### 公网部署提醒

- 服务器建议 Ubuntu 22.04/24.04，2 核 4 GB 起步；纯 CPU 跑 7B 会很慢，演示优先用带 GPU 的机器或只演示已有证据。
- `deploy/setup.sh` 首次执行会装依赖、建 `workshop` 用户、构建前端、装 systemd 与 Nginx；执行前先看脚本顶部注释。
- **Nginx 必须关闭代理缓冲**（`proxy_buffering off`），否则 SSE 会被攒成一整段；配置已写好，不要照抄普通反代模板。
- **uvicorn 必须 `--workers 1`**：诊断会话存在进程内存，多 worker 会导致会话找不到；量上来后再考虑 Redis，不要现在改。
- HTTPS 用 certbot；域名未备案时先用 IP + HTTP 自测，备案后再上证书。
- 部署后至少自测：`/health`、本地问答流式、云端升级、诊断打印四项。

---

## 9. 已知的坑（都是踩过的）

1. **Ollama 没启动**：后端能起来，但问答报模型连接错误；先确认 `11434` 端口有服务。
2. **没导入知识库**：检索集合为空，问答全部拒答；跑一次 `/api/kb/import`。空集合检索已修复为返回 `min_sim`，不会再 500。
3. **前端改了但 8000 没变**：生产态用的是 `dist`，必须 `npm run build`；开发态看 5173。
4. **SSE 在 Nginx 后面不流式**：检查 `proxy_buffering off`、`proxy_cache off`、`X-Accel-Buffering no`。
5. **诊断会话突然 404**：后端重启或多 worker；会话只在内存，重启即失效，演示前不要重启。
6. **云端路由失败**：先看 `backend/.env` 是否有 Key、网络/代理是否可达 `api.deepseek.com`；Ollama 本地调用要绕过代理（`NO_PROXY=localhost,127.0.0.1`）。
7. **PDF 版式跑偏**：`docs/tech-doc.html` 用 Chrome `Page.printToPDF` 生成，A4、`@page` 边距 0.5in/0.6in；改内容后目录页码要重填，页数必须 ≤30。
8. **引用卡片出现 Markdown 符号**：已在 `SourceCard.vue` 做纯文本化；新增引用样式时别直接渲染原文。
9. **DeepSeek Key 泄露风险**：只在 `backend/.env`；一旦误提交，立刻在平台吊销并换新 Key，再清理 Git 历史。
10. **示例数据不是真实工厂数据**：15 份文档为演示自编，数值是行业常识范围内的合理值，答辩时要说明。

---

## 10. 安全与合规约定

- 所有密钥只在 `backend/.env`；仓库只保留 `.env.example`，代码与文档中不得出现真实 Key。
- 部署时 `.env` 权限 `600`，属主为运行用户；服务器 SSH 用密钥，不用弱密码。
- 上传接口只收 `.md`/`.txt`，文件名去路径防目录穿越；删除是移入 `.trash`，不是物理删除。
- 云端只发送“问题 + 必要片段”，不上传整库；`ROUTE_MODE=kb_only` 可完全禁用云端，适合数据敏感演示。
- 仓库含 [MIT License](../LICENSE)，README 有公开仓库权限说明；评审无需账号即可访问。
- 技术文档附录 A 已如实说明 AI 参与范围与人工审查方式，答辩时按该口径讲，不夸大、不隐瞒。

---

## 11. 答辩与演示准备

**建议阅读顺序**：本文件 → [acceptance.md](acceptance.md)（知道做出了什么）→ [chunking.md](chunking.md) / [retrieval.md](retrieval.md)（为什么是 0.6）→ [rag-generation.md](rag-generation.md) / [routing.md](routing.md)（SSE 与端云）→ [diagnosis.md](diagnosis.md)（状态机）→ [frontend.md](frontend.md)（界面取舍）→ [mcp.md](mcp.md) / [deployment.md](deployment.md)。

**必须能脱稿说的五个数字**：

- 15 份文档、123 个切片；
- 阈值 0.6（正向最低 0.675、负向最高 0.522）；
- 本地 0.7833 / 云端升级 0.6589 / 拒答 0.4242；
- 诊断 6 步、报告 `CZ-20261105-070AF4`；
- 技术文档 25 页、视频 5–8 分钟。

**演示顺序**（与视频脚本一致）：本地问答带引用 → 拒答 → 云端升级 → 诊断完整链 + 打印 → MCP 终端 → 知识库管理 → 总结。每段都先给结论再操作，避免冷场。

**常见追问一句话答法**：

| 问题 | 答法 |
| --- | --- |
| 为什么不用通用大模型直接答？ | 车间要可溯源、数据不出厂；RAG 把答案锁在手册里，拒答比编造重要。 |
| 0.6 怎么来的？ | 30 条问句分正向/负向/灰区实测，0.6 是两侧都有余量的安全带中点，可复现。 |
| 云端会不会泄露数据？ | 只在本地低置信时发问题与必要片段，不发整库；可切 `kb_only` 完全禁用。 |
| 诊断为什么不用大模型？ | 故障排查要确定、可回退、每步有手册依据；状态机可控，大模型只做问答。 |
| MCP 有什么用？ | 把知识库检索变成标准工具，其他 AI 客户端/Agent 可直接调用，不用重复接后端。 |
| 前端为什么不用组件库？ | 工业现场需要高对比、大字号、状态色明确；自建令牌更可控，体积也更小。 |

---

## 12. 接手后的第一步清单

- [ ] 克隆仓库，按第 3 节跑通本地三视图；
- [ ] 跑第 5 节三条验收命令，确认结果与 `docs/evidence/` 一致；
- [ ] 读 `docs/index.md` 与 `acceptance.md`，能复述五个数字；
- [ ] 确认队伍信息，替换 `docs/video-script.md` 与技术文档占位；
- [ ] 拿到服务器信息后部署，补 README 在线演示链接；
- [ ] 录视频、平台提交；
- [ ] 每次改动后提交并 push，保持每日真实提交历史。

---

## 13. 维护约定

- **提交节奏**：每完成一个模块即提交并 push，禁止攒到最后；提交信息写清“做了什么、为什么”。
- **改检索/提示词/路由**：必须重跑校准或验收脚本，更新 `docs/evidence/` 与 `acceptance.md`，否则视为未验收。
- **改前端**：至少检查 1440 宽与 390×844 两个尺寸，问答、诊断、知识库三视图都要过一遍。
- **改材料**：技术文档 PDF 保持在 30 页内；目录页码、表格跨页表头、截图版本要同步。
- **不要提交**：`backend/.env`、`data/chroma/`、`data/kb_registry.json`、`node_modules/`、`dist/`、任务书原文。
- **对外动作**（部署到用户服务器、平台提交、发送材料）先确认再执行。

---

相关文档：[README](../README.md) · [设计说明索引](index.md) · [逐项验收](acceptance.md) · [部署手册](../deploy/README.md) · [视频脚本](video-script.md)
