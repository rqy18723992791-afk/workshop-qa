# 交接文档 · 车间智答

> 更新时间：2026-11-16
> 适用对象：接手的队友、指导教师、后续维护者
> 仓库：<https://github.com/rqy18723992791-afk/workshop-qa>（公开，MIT）
> 当前状态：**八项交付全部完成并验收留痕；公网演示已上线（https://workshop.runfeather.cn，2026-11-12 实测通过）；队伍信息已全量落位（重庆建筑工程职业学院「潜龙勿用」，提交 f2c3937）；技术文档新 PDF 已替换根目录（91f492a）；演示视频已出片（https://b23.tv/IAYNKPo）；平台报名提交待办（截止 2026-11-18 15:00）。**

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
| 演示稿三版（1500 / 2500 / 2000 字） | ✅ 定稿，队伍信息已替换 |
| README / LICENSE / 设计说明 / 验收记录 | ✅ 已入库 |
| 公网部署 | ✅ 已上线 <https://workshop.runfeather.cn>（详见 [deployment.md](deployment.md) 第 11 节） |
| 演示视频成片、平台报名提交 | ⬜ 用户侧 |

---

## 2. 现在最要紧的两件事（都在用户侧）

**① 队伍信息占位替换（2026-11-16 已完成，两处收尾见下）**

队伍信息已确认：重庆建筑工程职业学院「潜龙勿用」队，成员任秋羽、唐欣捷、吴城成，指导教师孙成杰、梁密。三版演示稿、`docs/tech-doc.html` 封面、README 团队信息、acceptance/handover 均已替换并提交（f2c3937，已 push）。

收尾 A——根目录技术文档 PDF：新 PDF 已生成并验证（25 页、封面为队伍真实信息、零占位、4 图完好），因旧文件被阅读器占用未替换。步骤：**关闭正在打开的 PDF**，然后执行：

```bash
cp "$TEMP/workshop-qa-techdoc.pdf" "D:/大学/竞赛/传智杯/车间智答-技术文档.pdf"
# 若临时件已丢，用 Chrome 重出（tech-doc.html 即最新源）：
"C:/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="D:/大学/竞赛/传智杯/车间智答-技术文档.pdf" "file:///D:/大学/竞赛/传智杯/docs/tech-doc.html"
```

完成后提交推送该 PDF。

收尾 B——docx 三版（`docs/*.docx`）：仍是占位版，未入库。md 已提交为正本，docx 可弃置或从 md 另存；如需 docx 同步替换：把三份 docx 里的【学校名称】→重庆建筑工程职业学院、【团队名称】→潜龙勿用（Word 里全局替换即可）。

**② 录制演示视频**

- 三版稿任选其一（现场限时选 2000 字版，普通用 2500 字版）。
- 规格：5–8 分钟、≥1080p、横屏、录屏 + 旁白，无需出镜。
- **数据口径**：本机演示讲 0.6 阈值（0.7833 / 0.6589 / 0.4242）；线上演示机讲 0.69 阈值（0.7928 / 0.6851 / 0.4308），稿子里已注明切换点，别混讲。
- 录制前按 [video-script.md](video-script.md) 第 0 节的清单逐项检查（Ollama 已启动、知识库已导入、云端问题提前试一次）。

**③ 平台报名与提交**

截止 **2026-11-18 15:00**（博学谷大赛通知口径；赛氪页头写 11-19，按最早口径准备）。内部冻结线：功能 11-15 冻结、材料 11-17 定稿、11-18 只提交。属账号与对外提交，按大赛通知操作。

提交前逐项核对（官方交付物仅 4 类）：

- [ ] 代码仓库 public：README 四项（项目介绍 / 技术架构 / 安装运行指南 / 团队信息）齐备、Git 历史完整、环境变量模板在根目录
- [x] 演示视频：5–8 分钟、MP4、≥1080p、普通话；链接已同步进 README（<https://b23.tv/IAYNKPo>）
- [ ] 技术文档：根目录 `车间智答-技术文档.pdf`，25 页 ≤30，封面为队伍真实信息（见 ① 收尾 A）
- [ ] 在线演示：<https://workshop.runfeather.cn>（可选加分，评审期间保持可用）

两个待确认口径：
- 赛道名：封面眉题 / 片头字幕现写「全国高校 AI WEB 开发挑战赛」，平台口径是「AI WEB网页开发挑战赛」，提交前统一其一；
- 报名信息：平台无「赛道-方向-作品-院校」命名要求；组别 C 组、选题方向「RAG 知识问答系统」只用于报名信息填写。

---

## 3. 关键链接与权限

| 事项 | 地址 / 说明 |
| --- | --- |
| 开源仓库 | <https://github.com/rqy18723992791-afk/workshop-qa> |
| 在线演示 | <https://workshop.runfeather.cn>（HTTPS，无需登录；备用 <http://1.14.203.217>） |
| 演示视频 | ✅ <https://b23.tv/IAYNKPo>（【重庆建筑工程职业学院 潜龙勿用团队】） |
| 技术文档 | 仓库根目录 `车间智答-技术文档.pdf` |
| 设计说明总索引 | [docs/index.md](index.md) |
| 逐项验收 | [docs/acceptance.md](acceptance.md) |
| 部署手册 | [deploy/README.md](../deploy/README.md) |

仓库为公开仓库，评审可直接克隆，无需账号或权限申请。推送权限在仓库所有者账号下，队友协作需所有者邀请；**任何密钥、服务器密码、平台账号都不要写进仓库或聊天记录**。

---

## 4. 五分钟跑起来（本机 Windows 开发环境）

### 4.1 前置

- Python 3.11+、Node.js 18+（推荐 20）
- Ollama，已拉取 `qwen2.5:7b-instruct-q4_K_M` 与 `bge-m3`
- DeepSeek Key 可选；不填则云端路由不可用，界面显示“云端未配置”

本机是便携版 Ollama，可执行文件在 `D:\tools\ollama\ollama.exe`，模型目录 `D:\tools\ollama-models`，未注册系统服务，**每次开机需手动启动**：

```bash
OLLAMA_MODELS="D:\tools\ollama-models" /d/tools/ollama/ollama.exe serve
```

### 4.2 配置

```bash
cd "D:\大学\竞赛\传智杯"
cp .env.example backend/.env
# 编辑 backend/.env，填 DEEPSEEK_API_KEY（可留空）
```

`backend/.env` 已被 `.gitignore` 排除，**永远不要提交**。

### 4.3 启动后端

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

### 4.4 启动前端

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

### 4.5 首次导入知识库

```bash
curl -X POST http://127.0.0.1:8000/api/kb/import
curl http://127.0.0.1:8000/api/kb/documents
```

15 份文档、123 个切片，首次向量化约 10–30 秒。`data/chroma/` 与 `data/kb_registry.json` 是运行时数据，**不在仓库里**；新克隆的仓库必须导入一次。

### 4.6 五个演示动作

1. 问“注塑机开机前需要检查什么？”→ 本地答案 + 引用卡片；
2. 问“如何做红烧肉？”→ 明确拒答，来源为空；
3. 问“注塑机螺杆磨损到什么程度必须更换？”→ 本地拒答后自动切云端，标签变蓝；
4. 进“故障排查”→ 走完不加热链路 → 生成处置单 → 打印 / 下载 Markdown；
5. 进“知识库”→ 检索测试台，改问题看相似度与阈值。

---

## 5. 目录地图（接手先看这些）

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
| `docs/` | 设计说明、验收、证据、演示稿三版 | 答辩复习 |
| `data/docs/` | 15 份示例知识库 | 自编演示数据 |

---

## 6. 验收怎么复现

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

预期结果（本机 2026-11-05 实测；演示机口径见第 9 节）：

| 项 | 结果 |
| --- | --- |
| 本地路径 | top-1 `0.7833`，`route=local`，`qwen2.5:7b`，引用 3 份文档 |
| 云端升级 | top-1 `0.6589`，本地拒答后 `route→cloud`，`deepseek-chat` |
| 拒答 | `0.4242 < 0.6`，`refused=true`，`sources=[]` |
| 诊断 | 6 步，结论 SSR 损坏，报告号 `CZ-20261105-070AF4` |
| MCP | `has_relevant=True`，`max_score=0.8078`，15 份文档 |

输出写入 `docs/evidence/`。每次改检索、提示词、路由后都应重跑并更新 [acceptance.md](acceptance.md)，不要把旧证据当新结果。

---

## 7. 关键参数（不要随手改）

| 参数 | 值 | 依据 |
| --- | --- | --- |
| 切片长度 / 重叠 | 600 字 / 80 字 | 中文手册段落完整性与上下文平衡 |
| 向量模型 | `bge-m3`，1024 维 | 中文检索效果 |
| 检索 top-k | 4 | 覆盖多文档又不过度稀释 |
| 拒答阈值 | **0.6**（本机）/ **0.69**（演示机） | 30 条问句校准的安全带中点；演示机 1.5B 生成层拒答弱，灰区问题易带引用编造，故调高 |
| 生成模型 | `qwen2.5:7b-instruct-q4_K_M`（本机）/ `qwen2.5:1.5b-instruct-q4_K_M`（演示机） | 8 GB 显存可跑，中文稳定；演示机 3.3 GB 内存装不下 7B |
| 路由模式 | `auto`（默认）/ `kb_only` | 低置信才上云 |
| 诊断会话 TTL | 2 小时，内存保存 | 重启即丢失，设计如此 |
| 处置单编号 | `CZ-YYYYMMDD-XXXXXX` | 按日期 + 随机后缀 |

阈值改动必须重新跑 `calibrate.py` 并更新校准记录；把阈值调低会放行无关问题，调高会误伤正常提问。

---

## 8. 已验收内容摘要

| 交付项 | 结论 | 证据入口 |
| --- | --- | --- |
| 前端问答界面 | ✅ SSE、引用卡片、三态路由标识、移动端 | `docs/assets/chat-*.png` |
| 拒答阈值校准 | ✅ 30 条问句，正向最低 0.675、负向最高 0.522 | [calibration.md](calibration.md) |
| 故障排查向导 | ✅ 6 步 + A4 处置单 + Markdown | [evidence/diagnosis-session.json](evidence/diagnosis-session.json) |
| 端云协同路由 | ✅ 三路径实测 | [route-local.json](evidence/route-local.json)、[route-cloud.json](evidence/route-cloud.json)、[route-refusal.json](evidence/route-refusal.json) |
| MCP 封装 | ✅ 官方客户端可调用 | [evidence/mcp-test.txt](evidence/mcp-test.txt) |
| 部署 | ✅ 本地生产态 + 公网实测通过（2026-11-12） | [deployment.md](deployment.md) 第 11 节 |
| 材料 | ✅ PDF 25 页、演示稿三版、README、LICENSE | 仓库根目录、docs/ |
| 设计说明 | ✅ 八页讲义式文档 | [index.md](index.md) |

---

## 9. 公网部署（已完成）与演示口径

- 线上：`https://workshop.runfeather.cn`（HTTPS 自动续期），腾讯云 2 核 3.3 GB 无 GPU，与多服务共存，独立 systemd 单元 `workshop-qa`，未动现有服务。
- **演示机口径与本机不同**：1.5B 模型、bge-m3 Q4 量化、阈值 **0.69**。线上演示讲 0.7928 / 0.6851 / 0.4308，本机讲 0.7833 / 0.6589 / 0.4242，别混讲；三版演示稿已注明切换点。
- 公网验收（证据在 `docs/evidence/`）：本地 0.7928 ≥ 0.69，首字 688 ms；云端升级 0.6851 < 0.69，首字 1211 ms；拒答 0.4308 升级云端后仍拒答；诊断 6 步 → SSR 损坏，报告 `CZ-20261112-839A03`。
- 关键配置已落实，不要改：Nginx `proxy_buffering off`（否则 SSE 不流式）、uvicorn `--workers 1`（诊断会话在内存）。
- 运维：`systemctl status workshop-qa`；日常更新 ssh `Luck` 后跑 `/opt/workshop-qa/deploy/deploy.sh`。
- 完整实录与同机踩坑（模型源限速改魔搭/hf-mirror、镜像补 `.so`、长会话断连用 nohup 落盘）见 [deployment.md](deployment.md) 第 11 节。

---

## 10. 已知的坑（都是踩过的）

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

## 11. 安全与合规约定

- 所有密钥只在 `backend/.env`；仓库只保留 `.env.example`，代码与文档中不得出现真实 Key。
- 部署时 `.env` 权限 `600`，属主为运行用户；服务器 SSH 用密钥，不用弱密码。
- 上传接口只收 `.md`/`.txt`，文件名去路径防目录穿越；删除是移入 `.trash`，不是物理删除。
- 云端只发送“问题 + 必要片段”，不上传整库；`ROUTE_MODE=kb_only` 可完全禁用云端，适合数据敏感演示。
- 仓库含 [MIT License](../LICENSE)，README 有公开仓库权限说明；评审无需账号即可访问。
- 技术文档附录 A 已如实说明 AI 参与范围与人工审查方式，答辩时按该口径讲，不夸大、不隐瞒。

---

## 12. 答辩与演示准备

**建议阅读顺序**：本文件 → [acceptance.md](acceptance.md)（知道做出了什么）→ [chunking.md](chunking.md) / [retrieval.md](retrieval.md)（为什么是 0.6）→ [rag-generation.md](rag-generation.md) / [routing.md](routing.md)（SSE 与端云）→ [diagnosis.md](diagnosis.md)（状态机）→ [frontend.md](frontend.md)（界面取舍）→ [mcp.md](mcp.md) / [deployment.md](deployment.md)。

**必须能脱稿说的五个数字**：

- 15 份文档、123 个切片；
- 阈值 0.6（正向最低 0.675、负向最高 0.522）；
- 本地 0.7833 / 云端升级 0.6589 / 拒答 0.4242；
- 诊断 6 步、报告 `CZ-20261105-070AF4`；
- 技术文档 25 页、视频 5–8 分钟。

**线上演示机口径**（只在线上演示时用）：阈值 0.69；0.7928 / 0.6851 / 0.4308；报告 `CZ-20261112-839A03`。

**演示顺序**（与三版演示稿一致）：本地问答带引用 → 拒答 → 云端升级 → 诊断完整链 + 打印 → MCP 终端 → 知识库管理 → 总结。每段都先给结论再操作，避免冷场。

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

## 13. 接手后的第一步清单

- [ ] 克隆仓库，按第 4 节跑通本地三视图；
- [ ] 跑第 6 节三条验收命令，确认结果与 `docs/evidence/` 一致；
- [ ] 读 `docs/index.md` 与 `acceptance.md`，能复述五个数字；
- [x] 确认队伍信息，替换三版演示稿与 `docs/tech-doc.html` 占位（2026-11-16）；
- [x] 公网部署并实测通过，README 已补在线演示链接；
- [x] 录视频（<https://b23.tv/IAYNKPo>）；平台提交待办；
- [ ] 每次改动后提交并 push，保持每日真实提交历史。

---

## 14. 维护约定

- **提交节奏**：每完成一个模块即提交并 push，禁止攒到最后；提交信息写清“做了什么、为什么”。
- **改检索/提示词/路由**：必须重跑校准或验收脚本，更新 `docs/evidence/` 与 `acceptance.md`，否则视为未验收。
- **改前端**：至少检查 1440 宽与 390×844 两个尺寸，问答、诊断、知识库三视图都要过一遍。
- **改材料**：技术文档 PDF 保持在 30 页内；目录页码、表格跨页表头、截图版本要同步。
- **不要提交**：`backend/.env`、`data/chroma/`、`data/kb_registry.json`、`node_modules/`、`dist/`、任务书原文。
- **对外动作**（部署到用户服务器、平台提交、发送材料）先确认再执行。

---

相关文档：[README](../README.md) · [设计说明索引](index.md) · [逐项验收](acceptance.md) · [部署手册](../deploy/README.md) · [演讲稿 1500 字](demo-speech.md) · [操作稿 2500 字](live-demo-script.md) · [操作稿 2000 字](live-demo-script-2000.md)
