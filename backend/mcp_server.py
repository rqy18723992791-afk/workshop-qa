"""车间智答 MCP Server：把知识库检索暴露为 MCP 工具。

启动方式（stdio）：
    backend/.venv/Scripts/python.exe backend/mcp_server.py

客户端配置示例（Claude Desktop / MCP Inspector）：
    {
      "mcpServers": {
        "workshop-qa": {
          "command": "D:/.../backend/.venv/Scripts/python.exe",
          "args": ["D:/.../backend/mcp_server.py"]
        }
      }
    }

工具：
- search_knowledge  向量检索知识库，返回片段、相似度与出处
- list_documents    查看知识库文档清单
"""
import json
import sys
from pathlib import Path

# 允许从任意工作目录启动：把 backend/ 加入 sys.path，app 包才能导入
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from app.services import kb  # noqa: E402

mcp = MCPServer(
    "workshop-qa",
    instructions="车间智答知识库：检索注塑机操作、点检、故障案例与安全规程。"
    "回答设备问题前先调用 search_knowledge，引用结果中的文档名与章节。",
)


@mcp.tool()
def search_knowledge(query: str, top_k: int = 4) -> str:
    """检索注塑车间知识库。

    Args:
        query: 自然语言问题，例如"料筒温度异常怎么排查"。
        top_k: 返回片段数，1-10，默认 4。

    Returns:
        JSON 字符串：query、max_score、has_relevant、hits（doc_title/doc_no/
        heading_path/score/text）。has_relevant=false 表示知识库没有相关内容，
        此时不应编造答案。
    """
    top_k = max(1, min(int(top_k), 10))
    result = kb.search(query, top_k=top_k)
    payload = {
        "query": result["query"],
        "max_score": result["max_score"],
        "min_sim": result["min_sim"],
        "has_relevant": result["has_relevant"],
        "hits": [
            {
                "doc_title": h["doc_title"],
                "doc_no": h["doc_no"],
                "category": h["category"],
                "heading_path": h["heading_path"],
                "score": h["score"],
                "text": h["text"],
            }
            for h in result["hits"]
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
def list_documents() -> str:
    """列出知识库中的文档（文档名、编号、类别、版本、切片数）。"""
    docs = kb.list_documents()
    payload = [
        {
            "doc_id": d["doc_id"],
            "title": d["title"],
            "doc_no": d["doc_no"],
            "category": d["category"],
            "version": d["version"],
            "chunk_count": d["chunk_count"],
        }
        for d in docs
    ]
    return json.dumps({"count": len(payload), "documents": payload}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
