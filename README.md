# 车间智答 · Workshop QA

面向智能制造一线的**本地化 AI 知识与故障排查助手**。

设备手册、点检标准、故障案例、安规规程进入知识库后，一线工人用自然语言提问，系统在工厂本地服务器用本地模型作答，**答案必须带出处**；复杂或低置信问题自动升级云端大模型兜底。

> 全国高校 AI Web 开发挑战赛（博学谷平台）C 组参赛作品 · 2026-11-18 提交

**卖点**：数据不出厂 · 离线可用 · 回答可溯源

## 功能特性（按开发优先级）

1. **知识库与 RAG 问答**（核心）
   - Markdown/txt 文档导入 → 自动切分 → 向量化 → 入库；文档管理列表（查看、删除、重建索引）
   - 提问后流式返回答案，答案下方列出引用来源（文档名 + 片段），点击查看原文
   - 检索不到相关内容时明确拒答（"知识库中暂无相关记录"），禁止编造
2. **故障排查向导**（Agent 工作流）
   - 注塑机故障诊断链：症状描述 → 分步追问/检查项（每步引用手册依据）→ 结构化「处置单」（现象、过程、结论、建议、出处），可导出/打印
   - 状态机实现，每一步可回退
3. **端云协同路由**（创新点）
   - 默认本地模型回答；检索相似度低于阈值或本地自评置信不足时自动升级 DeepSeek API
   - 界面明确标注本次回答走了"本地模型"还是"云端模型"及原因
4. **MCP 工具封装**
   - 知识库检索封装为 MCP Server 工具 `search_knowledge`，可被支持 MCP 的客户端调用
5. （选做）多模态：拍照描述故障，云端 VL 兜底

明确不做：用户注册/登录、权限管理、多设备类型、真实工厂数据、APP 客户端。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3 + Vite + TypeScript（工业风：深色、高对比、状态色明确） |
| 后端 | Python FastAPI（只做 AI 接入层：文档处理、检索、模型调用、路由） |
| 本地模型 | Ollama：Qwen 系列 7B/8B 量化版（显存不足降 4B）+ bge-m3 embedding |
| 向量库 | Chroma（本地持久化） |
| 云端兜底 | DeepSeek API（OpenAI 兼容） |
| 部署 | 自建 Linux 服务器，公网可访问 |

## 目录结构

```
├── README.md               # 项目说明（本文件）
├── .env.example            # 环境变量模板（复制为 backend/.env 使用）
├── backend/                # FastAPI 后端（AI 接入层）
│   ├── app/main.py         # 入口：/health + 路由挂载点
│   └── requirements.txt    # Python 依赖
├── frontend/               # Vue 3 单页应用
│   └── src/                # 源码
├── data/docs/              # 示例知识库文档（随代码交付）
├── data/chroma/            # 向量库持久化目录（运行时生成，不入库）
└── docs/                   # 核心模块设计说明（讲义式，答辩复习材料）
```

## 快速开始

### 1. 本地模型（Ollama）

```bash
# 安装 Ollama 后拉取模型（按本机显存选 7B/8B 量化版，跑不动降到 4B）
ollama pull qwen2.5:7b-instruct-q4_K_M
ollama pull bge-m3
```

### 2. 后端

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   /   Linux: source .venv/bin/activate
pip install -r requirements.txt
# 复制根目录 .env.example 为 backend/.env，填写 DEEPSEEK_API_KEY 等
uvicorn app.main:app --reload --port 8000
```

### 3. 前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173，/api 与 /health 已代理到后端 8000 端口
```

## 里程碑进度

- [x] 11-05 仓库初始化（README 骨架 + .gitignore + .env.example），脚手架跑通
- [ ] 11-06 Ollama + 模型就绪，示例文档 v1 入库，检索接口通
- [ ] 11-07 ~ 11-08 RAG 问答闭环（含引用与拒答）
- [ ] 11-09 ~ 11-10 前端界面成型，问答体验打磨
- [ ] 11-11 ~ 11-12 故障排查向导 + 处置单
- [ ] 11-13 端云路由 + MCP 封装
- [ ] 11-14 部署到服务器，公网自测
- [ ] 11-15 功能冻结，只修 bug；README 补全
- [ ] 11-16 演示视频脚本初稿
- [ ] 11-17 技术文档 PDF 初稿（≤30 页）

## 安全约定

- 所有密钥只走 `backend/.env`（已被 .gitignore 排除）；仓库只保留 `.env.example`
- 每次提交前自查：无真实密钥、无真实个人数据

## 文档索引

- [docs/index.md](docs/index.md) —— 核心模块设计说明索引（讲义式，答辩复习材料）
- [data/docs/README.md](data/docs/README.md) —— 示例知识库文档规范
