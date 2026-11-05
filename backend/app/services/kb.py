"""知识库服务：文档入库、删除、重建索引、检索。

存储分两部分：
- Chroma：向量 + 正文片段 + 每条片段的元数据（检索用）；
- data/kb_registry.json：文档级清单（文档名、类别、版本、切片数等，管理列表用）。

文档以「文档编号」为唯一键（无编号时用文件名），重复导入时先删旧切片再写入，
保证幂等；删除文档时把源文件移入 data/docs/.trash，避免误删不可恢复。
"""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import chromadb

from .. import config
from .chunking import chunk_document
from .embeddings import embed_texts, embed_query

_COLLECTION = "knowledge"
SUPPORTED_SUFFIXES = {".md", ".txt"}

_client = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return _client


def get_collection():
    return _get_client().get_or_create_collection(
        name=_COLLECTION,
        metadata={"hnsw:space": "cosine"},  # 余弦距离，相似度 = 1 - 距离
    )


def _reset_collection():
    try:
        _get_client().delete_collection(_COLLECTION)
    except Exception:
        pass  # 集合不存在时忽略


# ===== 文档清单（registry）=====

def load_registry() -> dict:
    if config.REGISTRY_PATH.exists():
        return json.loads(config.REGISTRY_PATH.read_text(encoding="utf-8"))
    return {"docs": {}, "updated_at": None}


def _save_registry(registry: dict) -> None:
    config.REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    registry["updated_at"] = datetime.now().isoformat(timespec="seconds")
    config.REGISTRY_PATH.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ===== 导入 =====

def _list_source_files() -> list[Path]:
    if not config.DOCS_DIR.exists():
        return []
    return [
        p for p in sorted(config.DOCS_DIR.iterdir())
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES and p.name.lower() != "readme.md"
    ]


def import_file(path: Path) -> dict:
    """导入/重导单个文件。返回文档记录。"""
    raw = path.read_text(encoding="utf-8")
    chunks = chunk_document(raw, path.name)
    if not chunks:
        raise ValueError(f"{path.name} 中没有可索引的内容")

    doc_id = chunks[0].doc_id
    collection = get_collection()
    # 幂等：同一文档编号重复导入时，先清掉旧切片
    collection.delete(where={"doc_id": doc_id})
    vectors = embed_texts([c.embed_text for c in chunks])
    collection.add(
        ids=[f"{doc_id}::{c.chunk_index}" for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[c.metadata() for c in chunks],
        embeddings=vectors,
    )

    record = {
        "doc_id": doc_id,
        "title": chunks[0].title,
        "category": chunks[0].category,
        "version": chunks[0].version,
        "date": chunks[0].date,
        "doc_no": chunks[0].doc_no,
        "file": path.name,
        "chunk_count": len(chunks),
        "content_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
        "imported_at": datetime.now().isoformat(timespec="seconds"),
    }
    registry = load_registry()
    registry["docs"][doc_id] = record
    _save_registry(registry)
    return record


def import_all(rebuild: bool = False) -> dict:
    """扫描 data/docs 全量导入；rebuild=True 时先清空索引与清单。"""
    if rebuild:
        _reset_collection()
        _save_registry({"docs": {}, "updated_at": None})

    imported, errors = [], []
    for path in _list_source_files():
        try:
            imported.append(import_file(path))
        except Exception as exc:  # 单个文件失败不影响其他文件
            errors.append({"file": path.name, "error": str(exc)})
    return {"imported": imported, "errors": errors, "count": len(imported)}


def import_uploaded_file(filename: str, content: bytes) -> dict:
    """保存上传文件到 data/docs 后入库。只接受 md/txt，按 UTF-8 解码。"""
    safe_name = Path(filename).name  # 去掉路径，防目录穿越
    if Path(safe_name).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("只支持 .md 或 .txt 文件")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("文件不是 UTF-8 编码，请另存为 UTF-8 后重试") from exc

    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.DOCS_DIR / safe_name
    path.write_text(text, encoding="utf-8")
    return import_file(path)


# ===== 文档管理 =====

def list_documents() -> list[dict]:
    return sorted(load_registry()["docs"].values(), key=lambda d: d["doc_id"])


def delete_document(doc_id: str) -> dict:
    registry = load_registry()
    record = registry["docs"].get(doc_id)
    if record is None:
        raise KeyError(doc_id)

    get_collection().delete(where={"doc_id": doc_id})
    # 源文件移入回收目录，而不是直接删除
    source = config.DOCS_DIR / record["file"]
    if source.exists():
        trash = config.DOCS_DIR / ".trash"
        trash.mkdir(exist_ok=True)
        shutil.move(str(source), str(trash / source.name))

    del registry["docs"][doc_id]
    _save_registry(registry)
    return record


# ===== 检索 =====

def search(query: str, top_k: int | None = None) -> dict:
    """向量检索，返回命中片段与相似度。

    score = 1 - 余弦距离；同时给出 max_score 与 has_relevant，
    供聊天接口判断"知识库无相关内容"时拒答。
    """
    query = query.strip()
    if not query:
        raise ValueError("查询内容不能为空")

    collection = get_collection()
    total = collection.count()
    if total == 0:
        return {
            "query": query,
            "hits": [],
            "max_score": 0.0,
            "min_sim": config.RETRIEVAL_MIN_SIM,
            "has_relevant": False,
        }

    k = min(top_k or config.RETRIEVAL_TOP_K, total)
    result = collection.query(
        query_embeddings=[embed_query(query)],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for text, meta, distance in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        hits.append(
            {
                "score": round(1.0 - float(distance), 4),
                "text": text,
                "doc_id": meta.get("doc_id", ""),
                "doc_title": meta.get("doc_title", ""),
                "doc_no": meta.get("doc_no", ""),
                "category": meta.get("category", ""),
                "version": meta.get("version", ""),
                "date": meta.get("date", ""),
                "file": meta.get("file", ""),
                "heading_path": meta.get("heading_path", ""),
                "chunk_index": meta.get("chunk_index", 0),
            }
        )

    max_score = max((h["score"] for h in hits), default=0.0)
    return {
        "query": query,
        "hits": hits,
        "max_score": round(max_score, 4),
        "min_sim": config.RETRIEVAL_MIN_SIM,
        "has_relevant": max_score >= config.RETRIEVAL_MIN_SIM,
    }
