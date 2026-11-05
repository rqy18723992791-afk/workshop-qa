# MCP 工具封装设计说明

> 对应代码：`backend/mcp_server.py`、`backend/scripts/test_mcp_client.py`
> 答辩可讲清的一句话：**把「知识库检索」从网页后端的一个函数，变成 MCP 协议里的标准工具；任何支持 MCP 的客户端（Claude Desktop、IDE、Inspector）都能直接调用，复用同一套向量检索和拒答判断。**

## 1. 为什么要做 MCP

当前知识库检索只服务于「车间智答」自己的前端。如果别的 AI 应用、IDE 插件或企业 Agent 想用这批厂内手册，通常只能：

- 复制一份检索代码过去；
- 或者调我们的 HTTP 接口，再自己写适配。

MCP（Model Context Protocol）解决的是「工具被发现和调用」的标准问题：Server 声明工具名、参数、说明，Client（通常是 AI 应用）自动发现并按 JSON Schema 调用。做成 MCP 后：

- 知识库能力可以脱离本项目的网页独立使用；
- 其他 Agent 不需要知道 Chroma、bge-m3、阈值这些细节；
- 工具描述里直接写「has_relevant=false 时不要编造答案」，把拒答约束传给调用方。

这也是比赛评分里「MCP / 工具集成」一项的直接落点。

## 2. Server 结构

使用 MCP Python SDK 的 `MCPServer`，stdio 传输：

```python
mcp = MCPServer(
    "workshop-qa",
    instructions="车间智答知识库：检索注塑机操作、点检、故障案例与安全规程。"
                 "回答设备问题前先调用 search_knowledge，引用结果中的文档名与章节。",
)

@mcp.tool()
def search_knowledge(query: str, top_k: int = 4) -> str: ...

@mcp.tool()
def list_documents() -> str: ...

mcp.run()
```

`@mcp.tool()` 会从函数签名和 docstring 自动生成工具描述与参数 schema，不需要手写协议消息。

### 2.1 两个工具

| 工具 | 参数 | 返回 |
| --- | --- | --- |
| `search_knowledge` | `query`（自然语言）、`top_k`（1–10，默认 4） | JSON：`query`、`max_score`、`min_sim`、`has_relevant`、`hits[]`（文档名、编号、类别、章节、分数、原文） |
| `list_documents` | 无 | JSON：文档数量 + 每份文档的编号、类别、版本、切片数 |

`top_k` 在函数内做 `max(1, min(int(top_k), 10))` 夹紧，防止客户端传 1000 把上下文撑爆。

### 2.2 为什么返回 JSON 字符串，而不是 Python 对象

MCP 工具的返回值最终要序列化成协议内容。直接返回 `json.dumps(..., ensure_ascii=False, indent=2)`：

- 结构稳定，客户端可以按字段解析；
- 中文不转义，模型和人都能直接读；
- 缩进格式便于调试时肉眼检查。

### 2.3 启动路径处理

MCP 客户端可能从任意工作目录启动进程。`mcp_server.py` 在导入 `app.services.kb` 前，把 `backend/` 插入 `sys.path`，保证「双击运行」和「从仓库根目录运行」都能找到包。这是 stdio Server 常见的坑：相对导入依赖 cwd。

## 3. 客户端配置

### 3.1 Claude Desktop / 通用 MCP 客户端

```json
{
  "mcpServers": {
    "workshop-qa": {
      "command": "D:/大学/竞赛/传智杯/backend/.venv/Scripts/python.exe",
      "args": ["D:/大学/竞赛/传智杯/backend/mcp_server.py"]
    }
  }
}
```

Linux 服务器上对应：

```json
{
  "mcpServers": {
    "workshop-qa": {
      "command": "/opt/workshop-qa/backend/.venv/bin/python",
      "args": ["/opt/workshop-qa/backend/mcp_server.py"]
    }
  }
}
```

前提：Ollama 已启动、知识库已导入（`curl -X POST :8000/api/kb/import`）。MCP Server 直接读 Chroma 和 Ollama，不依赖 FastAPI 进程。

### 3.2 命令行验收

```bash
backend/.venv/Scripts/python.exe backend/scripts/test_mcp_client.py
```

脚本用官方 `mcp.ClientSession` + `stdio_client` 启动 Server，依次：

1. `initialize` 握手；
2. `list_tools` 列出工具；
3. 调用 `search_knowledge("料筒温度异常怎么排查", top_k=3)`；
4. 调用 `list_documents`。

## 4. 实测结果（2026-11-05）

完整输出见 [evidence/mcp-test.txt](evidence/mcp-test.txt)。

```
== tools ==
- search_knowledge: 检索注塑车间知识库。
- list_documents: 列出知识库中的文档（文档名、编号、类别、版本、切片数）。

== call search_knowledge ==
has_relevant=True max_score=0.8078
  [0.8078] FC-T-001 三、排查步骤
  [0.7784] FC-T-001 五、预防措施
  [0.7544] FC-T-001 一、故障现象

== call list_documents ==
documents=15
```

三个结论：

- 工具能被标准客户端发现（2 个）；
- 检索结果与网页问答使用同一套 Chroma 数据，top-1 0.8078 命中故障案例卡；
- 文档清单返回 15 份，与知识库管理页一致。

## 5. 安全与边界

- **只读**：MCP 工具只做检索和列文档，不提供导入/删除，避免外部 Agent 误删知识库。
- **不返回密钥**：返回值只有文档片段和元数据，不包含 `.env`、路径、模型 Key。
- **不绕过阈值**：`has_relevant` 与网页端同一判断；调用方看到 `false` 应拒答或转人工，而不是硬编。
- **本地进程**：stdio 传输不监听端口，默认只有本机启动它的客户端能访问；如果要远程共享，需要额外的鉴权层，当前不做。

## 6. 取舍与后续

| 选择 | 取舍 |
| --- | --- |
| stdio 而非 HTTP/SSE | 零端口、零鉴权，适合本机 Agent；远程共享需另做网关 |
| 只封装检索 | 职责单一、可复用；问答生成仍由调用方决定，避免把 7B 模型强加给外部客户端 |
| 返回完整片段 | 调用方可以直接引用；片段较长时上下文占用高，可加 `max_chars` 参数 |
| 不做缓存 | 每次调用实时检索，数据最新；高频调用可加 Redis 缓存 |

## 7. 答辩可能被问到的问题

- **MCP 和普通 HTTP API 有什么区别？** HTTP API 需要调用方知道 URL、参数、鉴权；MCP 是标准化的工具发现协议，客户端启动 Server 后自动拿到工具列表和 JSON Schema，模型可以直接决定调用哪个工具。
- **为什么不做成远程 MCP？** 比赛演示和厂内使用都是本机/内网，stdio 最简单也最安全；远程化需要处理鉴权、多租户、限流，超出当前范围。
- **MCP 返回的分数和网页一致吗？** 一致，都是 `kb.search()` 的 `1 - distance`；阈值也读同一个 `RETRIEVAL_MIN_SIM`。
- **如果客户端不遵守 has_relevant 提示怎么办？** 工具描述里明确写了「此时不应编造答案」；协议层无法强制，但可以把这条约束同时写进调用方的系统提示词。
