"""RAG 问答服务：检索 → 拼上下文 → 本地模型生成 → 引用来源。

拒答采用两层策略：
1. 检索层：最高相似度低于 RETRIEVAL_MIN_SIM 时直接拒答，不调用大模型，
   避免模型拿无关片段强行发挥；
2. 生成层：系统提示词强制"只能依据资料回答，资料不足就拒绝"，
   覆盖"问题属于注塑领域但知识库没有答案"的边界情况。

流式接口把「来源」作为第一个事件先发给前端，再逐段发送答案增量，
这样用户先看到出处，再看到生成内容。
"""
import json

import ollama

from .. import config
from . import kb

REFUSAL = "知识库中暂无相关记录。"
SYSTEM_PROMPT = """你是"车间智答"，面向注塑车间一线操作工的设备知识与故障排查助手。

回答规则：
1. 只允许使用【参考资料】中的信息作答，禁止使用任何常识、外部知识或推测补充。
2. 如果【参考资料】不足以回答问题，必须只输出：知识库中暂无相关记录。
3. 回答要具体、可执行：保留步骤编号、温度/压力等数值和单位。
4. 引用资料中的内容时，在句末用 [编号] 标注来源，编号必须与参考资料编号一致。
5. 使用简洁的中文，先给结论或关键数值，再列步骤。
6. 不得编造资料中没有的报警代码、参数值或操作步骤。"""

_client = ollama.Client(host=config.OLLAMA_BASE_URL, timeout=300)


def _build_context(hits: list[dict]) -> str:
    blocks = []
    for index, hit in enumerate(hits, start=1):
        blocks.append(
            f"[{index}] 文档：{hit['doc_title']}（{hit['doc_no']}）"
            f"｜章节：{hit['heading_path']}\n{hit['text']}"
        )
    return "\n\n".join(blocks)


def _to_sources(hits: list[dict]) -> list[dict]:
    """给前端的引用来源：文档名 + 原文片段 + 定位信息。"""
    return [
        {
            "index": index,
            "doc_id": hit["doc_id"],
            "doc_title": hit["doc_title"],
            "doc_no": hit["doc_no"],
            "category": hit["category"],
            "heading_path": hit["heading_path"],
            "score": hit["score"],
            "text": hit["text"],
        }
        for index, hit in enumerate(hits, start=1)
    ]


def _messages(query: str, hits: list[dict]) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"【参考资料】\n{_build_context(hits)}\n\n【用户问题】\n{query}",
        },
    ]


def _options() -> dict:
    return {"temperature": 0.1, "num_ctx": config.LLM_NUM_CTX}


def _is_refusal(text: str) -> bool:
    """模型输出以拒答语开头即视为拒答（允许后面没有多余内容）。"""
    return text.strip().startswith("知识库中暂无相关记录")


def answer(query: str, top_k: int | None = None) -> dict:
    """非流式问答，供测试、MCP 工具和后续诊断向导复用。"""
    result = kb.search(query, top_k=top_k)
    base = {
        "query": query,
        "route": "local",
        "model": config.LLM_MODEL,
        "max_score": result["max_score"],
    }

    if not result["has_relevant"]:
        return {**base, "answer": REFUSAL, "refused": True, "sources": []}

    response = _client.chat(
        model=config.LLM_MODEL,
        messages=_messages(query, result["hits"]),
        stream=False,
        keep_alive="30m",
        options=_options(),
    )
    text = (response["message"]["content"] or "").strip()
    refused = _is_refusal(text)
    return {
        **base,
        "answer": text,
        "refused": refused,
        "sources": [] if refused else _to_sources(result["hits"]),
    }


def stream_answer(query: str, top_k: int | None = None):
    """逐事件产出问答流，事件字典由路由层序列化为 SSE。

    事件类型：
    - meta   来源列表、路由、检索得分（先于正文发送）
    - delta  答案增量
    - done   结束，带完整答案与是否拒答
    - error  模型或检索异常
    """
    try:
        result = kb.search(query, top_k=top_k)
    except Exception as exc:  # 检索阶段失败（如 Ollama 未启动）
        yield {"type": "error", "message": f"检索失败：{exc}"}
        return

    has_relevant = result["has_relevant"]
    yield {
        "type": "meta",
        "route": "local",
        "model": config.LLM_MODEL,
        "max_score": result["max_score"],
        "min_sim": result["min_sim"],
        "refused": not has_relevant,
        "sources": [] if not has_relevant else _to_sources(result["hits"]),
    }

    if not has_relevant:
        yield {"type": "delta", "content": REFUSAL}
        yield {"type": "done", "answer": REFUSAL, "refused": True}
        return

    collected: list[str] = []
    try:
        for part in _client.chat(
            model=config.LLM_MODEL,
            messages=_messages(query, result["hits"]),
            stream=True,
            keep_alive="30m",
            options=_options(),
        ):
            piece = (part["message"]["content"] or "")
            if piece:
                collected.append(piece)
                yield {"type": "delta", "content": piece}
    except Exception as exc:
        yield {"type": "error", "message": f"生成失败：{exc}"}
        return

    text = "".join(collected).strip()
    yield {"type": "done", "answer": text, "refused": _is_refusal(text)}


def sse(event: dict) -> str:
    """把事件字典编码为 SSE 数据帧。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
