"""车间智答 —— FastAPI 后端入口。

只做 AI 接入层：文档处理、检索、模型调用、路由。
不做用户系统与权限（任务书明确排除）。

路由规划（模块完成后在 docs/ 留设计说明）：
  11-06  /api/kb/*      文档导入、列表、删除、重建索引、检索   （routers/kb.py）
  11-07  /api/chat/*    RAG 问答：流式 + 引用 + 两层拒答         （routers/chat.py）
  11-12  /api/diag/*    故障排查向导状态机 + 处置单              （routers/diag.py）
  11-13  端云协同路由    已集成在 chat 服务；MCP 见 backend/mcp_server.py
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .routers import chat, diag, kb

app = FastAPI(
    title="车间智答 API",
    description="面向智能制造一线的本地化 AI 知识与故障排查助手 —— AI 接入层",
    version="0.3.0",
)

# 开发期放开跨域（前端 dev 服务器与后端端口不同）；
# 生产环境同域由后端托管前端静态文件，或由 Nginx 反代。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(kb.router)
app.include_router(chat.router)
app.include_router(diag.router)

# 生产部署：前端 npm run build 后由后端直接托管 dist，单端口即可完整运行。
# 开发时 dist 不存在，前端走 Vite dev server（5173 端口代理 /api）。
_FRONTEND_DIST = config.BASE_DIR / "frontend" / "dist"
if (_FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")


@app.get("/", include_in_schema=False)
def index():
    index_file = _FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {
        "service": "workshop-qa",
        "message": "前端尚未构建。开发模式请访问 Vite 的 5173 端口，"
        "或执行 cd frontend && npm run build 后重试。",
    }


@app.get("/health", tags=["系统"])
def health() -> dict:
    """健康检查：前端首页状态卡与部署自测调用。"""
    return {
        "status": "ok",
        "service": "workshop-qa",
        "version": "0.3.0",
        "ollama_base_url": config.OLLAMA_BASE_URL,
        "llm_model": config.LLM_MODEL,
        "embed_model": config.EMBED_MODEL,
        "retrieval_min_sim": config.RETRIEVAL_MIN_SIM,
        "route_mode": config.ROUTE_MODE,
        "cloud_configured": bool(config.DEEPSEEK_API_KEY),
        "frontend_built": (_FRONTEND_DIST / "index.html").is_file(),
    }
