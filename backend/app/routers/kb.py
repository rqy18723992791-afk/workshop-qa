"""知识库 API：导入、上传、列表、删除、重建索引、检索。"""
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ..services import kb

router = APIRouter(prefix="/api/kb", tags=["知识库"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="检索问题")
    top_k: int | None = Field(default=None, ge=1, le=20, description="返回条数")


def _is_ollama_down(exc: Exception) -> bool:
    """Ollama 未启动 / 模型未拉取时，给前端一个可读的 503。"""
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(k in text for k in ("connection", "refused", "connect", "not found", "pull"))


@router.post("/import", summary="扫描 data/docs 导入全部文档")
def import_documents(rebuild: bool = False) -> dict:
    try:
        return kb.import_all(rebuild=rebuild)
    except Exception as exc:
        if _is_ollama_down(exc):
            raise HTTPException(503, "本地嵌入模型不可用：请确认 Ollama 已启动且已拉取 bge-m3") from exc
        raise


@router.post("/reindex", summary="清空索引并全量重建")
def reindex() -> dict:
    return import_documents(rebuild=True)


@router.post("/upload", summary="上传 md/txt 文档并入库")
def upload_document(file: UploadFile = File(...)) -> dict:
    # 同步路由：FastAPI 会放到线程池执行，避免阻塞事件循环；
    # 入库包含同步的向量化调用（CPU/GPU 推理），放在线程池更合适。
    if not file.filename:
        raise HTTPException(400, "缺少文件名")
    content = file.file.read()
    try:
        return kb.import_uploaded_file(file.filename, content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        if _is_ollama_down(exc):
            raise HTTPException(503, "本地嵌入模型不可用：请确认 Ollama 已启动且已拉取 bge-m3") from exc
        raise


@router.get("/documents", summary="文档列表")
def list_documents() -> dict:
    documents = kb.list_documents()
    return {"count": len(documents), "documents": documents}


@router.delete("/documents/{doc_id}", summary="删除文档（索引 + 源文件移入回收目录）")
def delete_document(doc_id: str) -> dict:
    try:
        return kb.delete_document(doc_id)
    except KeyError as exc:
        raise HTTPException(404, f"文档不存在：{doc_id}") from exc


@router.post("/search", summary="向量检索")
def search_knowledge(req: SearchRequest) -> dict:
    try:
        return kb.search(req.query, top_k=req.top_k)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        if _is_ollama_down(exc):
            raise HTTPException(503, "本地嵌入模型不可用：请确认 Ollama 已启动且已拉取 bge-m3") from exc
        raise
