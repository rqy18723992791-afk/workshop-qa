"""调用 Ollama 的 embedding 接口，把文本批量转成向量。

为什么不用 Chroma 自带的 embedding function：
- 我们明确用中文向量模型 bge-m3，显式传入向量更可控，也避免 Chroma
  在首次写入时隐式下载 onnx 模型（车间环境可能无外网）；
- 批量接口一次请求多条文本，比逐条调用快得多。
"""
import ollama

from .. import config

_client = ollama.Client(host=config.OLLAMA_BASE_URL, timeout=180)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """返回与输入等长的向量列表；空输入直接返回空。"""
    if not texts:
        return []
    vectors: list[list[float]] = []
    for start in range(0, len(texts), config.EMBED_BATCH):
        batch = texts[start:start + config.EMBED_BATCH]
        # keep_alive=30m：避免模型频繁卸载/重载。实测冷加载约 25 s，
        # 驻留后单条查询约 0.1 s，对问答体验影响巨大。
        response = _client.embed(model=config.EMBED_MODEL, input=batch, keep_alive="30m")
        batch_vectors = response["embeddings"]
        if len(batch_vectors) != len(batch):
            raise RuntimeError(
                f"embedding 返回数量不匹配：请求 {len(batch)} 条，返回 {len(batch_vectors)} 条"
            )
        vectors.extend(batch_vectors)
    return vectors


def embed_query(text: str) -> list[float]:
    """单条查询向量。"""
    return embed_texts([text])[0]
