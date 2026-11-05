# 逐项验收记录

> 验收日期：2026-11-05
> 环境：Windows 11 · Ollama 本地 `qwen2.5:7b-instruct-q4_K_M` + `bge-m3` · FastAPI `127.0.0.1:8000` · 知识库 15 份文档 / 123 切片 · 阈值 0.6
> 方法：接口脚本实测 + 浏览器真实交互（headless Chrome CDP）+ 截图/PDF 留痕。原始数据在 [evidence/](evidence/)。

## 总览

| # | 验收项 | 对应任务书标准 | 结果 |
| --- | --- | --- | --- |
| 1 | 前端问答界面 | 流式返回、引用来源、点击查看原文 | ✅ 通过 |
| 2 | 拒答阈值校准 | 20–30 条问句标定并留记录 | ✅ 通过（30 条） |
| 3 | 故障排查向导 | 完整走完一条链并生成处置单，可回退、可导出 | ✅ 通过 |
| 4 | 端云协同路由 | 一易一难触发两种路径，界面标注路径与原因 | ✅ 通过 |
| 5 | MCP 工具封装 | MCP 客户端成功调用并返回检索结果 | ✅ 通过 |
| 6 | 部署 | 本地全链路跑通，部署脚本/说明齐备；公网待服务器 | 🟡 本地通过，公网待办 |
| 7 | 材料初稿 | 技术文档 PDF ≤30 页；视频脚本 5–8 分钟 | ✅ 初稿完成 |
| 8 | 设计说明 | 每个核心模块一页讲义式 docs/ | ✅ 完成 |

## 1. 前端问答界面

**标准**：消费 SSE 流式接口；引用来源卡片可查看原文；本地/云端路由标识可见；工业风可演示。

**实测**：

| 检查点 | 结果 |
| --- | --- |
| SSE 流式 | 答案逐字出现；事件序列 `meta → delta → done`；首字 0.25 s（本地热态） |
| 引用卡片 | 4 条来源，展示文档名、编号、章节、相似度、原文；正文 `[1]` 点击可定位并展开 |
| 路由标识 | 绿色「本地模型 · 知识库作答」/ 蓝色「云端模型 · 通用建议」/「已拒答」三态 |
| 右侧链路监视 | 实时显示 top-1 分数、阈值、路由原因、首字/总耗时、来源数 |
| 空状态 | 4 个示例问题卡片，点击直接提问 |
| 停止生成 | 生成中按钮变「停止」，中止后提示内容可能不完整 |
| 移动端 | 390×844 三视图可操作，无横向溢出 |
| 视觉 | 深色工业风、状态色明确、字号适合车间阅读 |

**证据**：[chat-local.png](assets/chat-local.png)、[chat-cloud.png](assets/chat-cloud.png)、[chat-welcome.png](assets/chat-welcome.png)

## 2. 拒答阈值校准

**标准**：20–30 条问句标定阈值并留校准记录。

**实测**：30 条问句（正向 15 / 负向 8 / 灰区 7），只检索不生成。

| 指标 | 数值 |
| --- | --- |
| 正向最低分 | 0.675 |
| 正向平均分 | 0.754 |
| 负向最高分 | 0.522 |
| 负向平均分 | 0.378 |
| 灰区范围 | 0.436～0.617 |
| 最终阈值 | **0.6**（安全带中点，两侧各约 0.075 余量） |

旧阈值 0.5 会放行「手机屏幕碎了怎么办」（0.522）；0.6 在检索层直接挡住。完整 30 条数据、过拟合修正过程见 [calibration.md](calibration.md) 与 [calibration-data.json](calibration-data.json)。

**证据**：[retrieval.md](retrieval.md)、`backend/scripts/calibrate.py` 可复现。

## 3. 故障排查向导

**标准**：从症状开始完整走完一条链并生成处置单；状态机、每步手册依据、可回退、可导出/打印。

**实测**：

| 检查点 | 结果 |
| --- | --- |
| 完整链路 | 安全确认 → 现象判断 → 加热圈电阻 → 接线端子 → 热电偶比对 → 固态继电器，共 6 步 |
| 每步依据 | 均引用 `FC-T-001` 对应章节，界面可展开原文 |
| 结论 | 固态继电器（SSR）损坏，需更换（立即处置） |
| 处置单字段 | 编号、设备、现象、过程表、结论、处置建议、安全提示、6 条依据、签字栏 |
| 报告编号 | `CZ-20261105-070AF4`（格式 `CZ-YYYYMMDD-XXXXXX`） |
| 回退 | 从完成态回退一步回到 `ssr_test`，结论清空，可重新作答 |
| 打印 | Chrome `Page.printToPDF` 输出 2 页 A4，无右侧裁切 |
| Markdown | `/report.md` 可下载，内容与网页同源 |

**证据**：[diagnosis-session.json](evidence/diagnosis-session.json)、[diagnosis-report.md](evidence/diagnosis-report.md)、[diag-report-print.png](assets/diag-report-print.png)、[diag-step.png](assets/diag-step.png)

## 4. 端云协同路由

**标准**：一易一难两个问题触发本地/云端两种路径；界面标注路径与原因；各留一次实测记录。

**实测**：

| 路径 | 问题 | top-1 | 结果 |
| --- | --- | --- | --- |
| 本地 | 注塑机开机前需要检查什么？ | 0.7833 | `route=local`，`qwen2.5:7b`，首字 1.0 s，引用 3 份文档 |
| 云端升级 | 注塑机螺杆磨损到什么程度必须更换？ | 0.6589 | 本地拒答 → `route→cloud`，`deepseek-chat`，首字 3.3 s，标注【通用建议】 |
| 拒答 | 如何做红烧肉？ | 0.4242 | `refused=true`，`sources=[]`，界面「已拒答」 |

事件序列核实：云端用例为 `meta → route(cloud) → delta → done`，本地拒答文本被缓冲，未提前泄漏。

**证据**：[route-local.json](evidence/route-local.json)、[route-cloud.json](evidence/route-cloud.json)、[route-refusal.json](evidence/route-refusal.json)、[chat-cloud.png](assets/chat-cloud.png)

## 5. MCP 工具封装

**标准**：MCP 客户端/调试工具成功调用并返回检索结果。

**实测**：官方 `mcp.ClientSession` + `stdio_client`：

- `list_tools` 返回 `search_knowledge`、`list_documents`；
- `search_knowledge("料筒温度异常怎么排查", top_k=3)` → `has_relevant=True`，`max_score=0.8078`，top-3 均命中 `FC-T-001`；
- `list_documents` → 15 份。

**证据**：[mcp-test.txt](evidence/mcp-test.txt)、[mcp.md](mcp.md)

## 6. 部署

**标准**：本地全链路跑通，部署脚本与说明备好；服务器信息到位后完成公网部署与自测。

**已完成**：

- 生产态单端口验证：`npm run build` 后 FastAPI 托管 `dist`，`/health` 返回 `frontend_built=true`；
- 三视图、SSE 本地/云端、诊断打印均在 8000 端口实测通过；
- `deploy/setup.sh`（首次初始化）、`deploy/deploy.sh`（日常更新）、systemd 单元、Nginx 配置（关闭缓冲保证 SSE）、[deploy/README.md](../deploy/README.md) 全部就绪；
- Bash 语法检查通过；systemd/Nginx 配置按 Ubuntu 22.04/24.04 编写。

**未完成**：公网部署。需要用户提供服务器公网 IP、SSH 方式、域名/备案情况、配置与安全组；拿到后执行 `setup.sh` 并完成外网四项自测。

**证据**：[deployment.md](deployment.md)、`deploy/`。

## 7. 材料初稿

| 材料 | 状态 | 位置 |
| --- | --- | --- |
| 技术文档 PDF（≤30 页） | ✅ 初稿 | 仓库根目录 `车间智答-技术文档.pdf` |
| 视频脚本（5–8 分钟） | ✅ 定稿结构，队伍信息占位 | [video-script.md](video-script.md) |
| README（简介/链接/亮点/仓库地址/权限说明） | ✅ | [README.md](../README.md) |
| LICENSE | ✅ MIT | [LICENSE](../LICENSE) |

技术文档含「AI 生成代码说明」附录，如实列出 AI 参与范围与人工审查方式。

## 8. 设计说明

| 模块 | 文档 |
| --- | --- |
| 切分入库 | [chunking.md](chunking.md) |
| 检索与阈值 | [retrieval.md](retrieval.md)、[calibration.md](calibration.md) |
| RAG 生成 | [rag-generation.md](rag-generation.md) |
| 端云路由 | [routing.md](routing.md) |
| 诊断状态机 | [diagnosis.md](diagnosis.md) |
| MCP | [mcp.md](mcp.md) |
| 前端 | [frontend.md](frontend.md) |
| 部署 | [deployment.md](deployment.md) |

## 未完成项与原因

| 项 | 原因 | 下一步 |
| --- | --- | --- |
| 公网部署 | 缺服务器信息（IP、SSH、域名/备案、配置、安全组） | 用户提供后执行 `deploy/setup.sh` 并外网自测 |
| 演示视频成片 | 需真人旁白/剪辑与队伍信息 | 用户按 [video-script.md](video-script.md) 录制；我负责演示数据与脚本 |
| 平台报名、缴费、最终提交 | 属用户账号与对外提交 | 用户处理 |
| 团队信息、指导教师 | 用户落实 | 替换脚本与技术文档中的占位 |

## 需要用户处理

1. 提供服务器信息（不要发密码到仓库；可用 SSH 密钥或临时方式）。
2. 确认队伍名称、成员、学校、指导教师，替换视频脚本与技术文档占位。
3. 按脚本录制 5–8 分钟、≥1080p 视频。
4. 平台报名、缴费、上传作品与技术文档。
