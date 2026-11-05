"""RAG 问答 API：非流式 + SSE 流式。"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..services import chat

router = APIRouter(prefix="/api", tags=["问答"])


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="用户问题")
    top_k: int | None = Field(default=None, ge=1, le=20, description="检索条数")


@router.post("/chat", summary="RAG 问答（非流式，返回答案与引用来源）")
def chat_once(req: ChatRequest) -> dict:
    try:
        return chat.answer(req.query, top_k=req.top_k)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, f"问答服务不可用：{exc}") from exc


@router.post("/chat/stream", summary="RAG 问答（SSE 流式：meta 来源 → delta 增量 → done）")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    def generate():
        yield from (chat.sse(event) for event in chat.stream_answer(req.query, top_k=req.top_k))

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 反代时禁用缓冲，保证逐字输出
        },
    )
