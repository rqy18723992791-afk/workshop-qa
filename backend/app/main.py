"""车间智答 —— FastAPI 后端入口。

只做 AI 接入层：文档处理、检索、模型调用、路由。
不做用户系统与权限（任务书明确排除）。

路由规划（按里程碑逐步落地，模块完成后在 docs/ 留设计说明）：
  11-06  /api/kb/*      文档导入、列表、删除、重建索引、检索   （routers/kb.py）
  11-07  /api/chat/*    RAG 问答：流式 + 引用 + 拒答             （routers/chat.py）
  11-12  /api/diag/*    故障排查向导状态机                       （routers/diag.py）
  11-13  /api/route/*   端云协同路由；MCP Server 工具 search_knowledge
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .routers import kb

app = FastAPI(
    title="车间智答 API",
    description="面向智能制造一线的本地化 AI 知识与故障排查助手 —— AI 接入层",
    version="0.2.0",
)

# 开发期放开跨域（前端 dev 服务器与后端端口不同）；
# 生产环境由 Nginx 同域反代，不存在跨域问题。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(kb.router)


@app.get("/health", tags=["系统"])
def health() -> dict:
    """健康检查：前端首页状态卡与部署自测调用。"""
    return {
        "status": "ok",
        "service": "workshop-qa",
        "version": "0.2.0",
        "ollama_base_url": config.OLLAMA_BASE_URL,
        "llm_model": config.LLM_MODEL,
        "embed_model": config.EMBED_MODEL,
        "retrieval_min_sim": config.RETRIEVAL_MIN_SIM,
    }
