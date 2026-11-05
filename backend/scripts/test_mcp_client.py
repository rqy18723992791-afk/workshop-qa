"""MCP 验收脚本：以标准 MCP 客户端连接 stdio server，列出并调用工具。

运行：
    backend/.venv/Scripts/python.exe backend/scripts/test_mcp_client.py
"""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BACKEND_DIR = Path(__file__).resolve().parents[1]
SERVER = BACKEND_DIR / "mcp_server.py"


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        cwd=str(BACKEND_DIR),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("== tools ==")
            for tool in tools.tools:
                print(f"- {tool.name}: {(tool.description or '').splitlines()[0]}")

            print("\n== call search_knowledge ==")
            result = await session.call_tool(
                "search_knowledge",
                {"query": "料筒温度异常怎么排查", "top_k": 3},
            )
            text = "\n".join(
                block.text for block in result.content if hasattr(block, "text")
            )
            data = json.loads(text)
            print(f"has_relevant={data['has_relevant']} max_score={data['max_score']}")
            for hit in data["hits"]:
                print(f"  [{hit['score']}] {hit['doc_no']} {hit['heading_path']}")

            print("\n== call list_documents ==")
            result = await session.call_tool("list_documents", {})
            text = "\n".join(
                block.text for block in result.content if hasattr(block, "text")
            )
            docs = json.loads(text)
            print(f"documents={docs['count']}")


if __name__ == "__main__":
    asyncio.run(main())
