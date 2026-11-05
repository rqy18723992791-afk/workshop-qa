"""RAG 问答与端云协同路由。

回答路径：
- 本地路径：检索命中 → Qwen 依据编号资料作答（带引用）。检索不命中或模型
  判断资料不足时，若开启"智能协同"则升级 DeepSeek。
- 云端路径：DeepSeek 基于同一批检索片段作答；资料不足可补充通用工程建议，
  但必须以【通用建议】标注，且不得编造具体参数。与注塑无关的问题云端也会拒答。

流式接口先发 meta（来源 / 路由），必要时再发 route 事件切换路径，最后 done。
本地模型输出拒答语时才切换到云端，切换前的拒答文本会被缓冲、不发给前端，
避免界面先出现"暂无记录"又突然变成云端答案。
"""
import json

import ollama

from .. import config
from . import cloud, kb

REFUSAL = "知识库中暂无相关记录。"
ROUTE_AUTO = "auto"
ROUTE_KB_ONLY = "kb_only"

SYSTEM_PROMPT = """你是"车间智答"，面向注塑车间一线操作工的设备知识与故障排查助手。

回答规则：
1. 只允许使用【参考资料】中的信息作答，禁止使用任何常识、外部知识或推测补充。
2. 如果【参考资料】不足以回答问题，必须只输出：知识库中暂无相关记录。
3. 回答要具体、可执行：保留步骤编号、温度/压力等数值和单位。
4. 引用资料中的内容时，在句末用 [编号] 标注来源，编号必须与参考资料编号一致。
5. 使用简洁的中文，先给结论或关键数值，再列步骤。
6. 不得编造资料中没有的报警代码、参数值或操作步骤。"""

CLOUD_SYSTEM_PROMPT = """你是"车间智答"的云端协同专家，服务注塑车间一线人员。

回答规则：
1. 只回答注塑机、注塑工艺、模具、设备维护与车间安全相关问题；与这些无关的问题，必须只输出：知识库中暂无相关记录。
2. 【参考资料】能回答的部分优先采用，并在句末用 [编号] 标注；编号必须与参考资料一致。
3. 不要因为资料不全就拒绝回答注塑领域的问题。资料不足的部分直接以【通用建议】开头给出通用工程经验，并提示"需现场确认"；不得编造具体报警代码、型号参数或厂家数据。
4. 回答开头不要写"知识库中暂无相关记录"，除非问题与注塑完全无关。
5. 涉及拆机、带电、高温作业，必须提醒断电挂牌、冷却，并由持证人员操作。
6. 中文回答，先结论后步骤，保留数值与单位。"""

_client = ollama.Client(host=config.OLLAMA_BASE_URL, timeout=300)


# ===== 公共拼装 =====

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


def _cloud_messages(query: str, hits: list[dict], with_context: bool) -> list[dict]:
    if with_context and hits:
        user = f"【参考资料】\n{_build_context(hits)}\n\n【用户问题】\n{query}"
    else:
        user = f"【用户问题】\n{query}"
    return [
        {"role": "system", "content": CLOUD_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _options() -> dict:
    return {"temperature": 0.1, "num_ctx": config.LLM_NUM_CTX}


def _is_refusal(text: str) -> bool:
    """模型输出以拒答语开头即视为拒答（允许后面没有多余内容）。"""
    return text.strip().startswith("知识库中暂无相关记录")


def _mode(route_mode: str | None) -> str:
    mode = (route_mode or config.ROUTE_MODE).strip().lower()
    return ROUTE_KB_ONLY if mode == ROUTE_KB_ONLY else ROUTE_AUTO


def _local_reason(max_score: float) -> str:
    return (
        f"检索最高相似度 {max_score:.2f} ≥ 阈值 {config.RETRIEVAL_MIN_SIM:.2f}，"
        "由本地模型依据知识库作答"
    )


def _cloud_low_reason(max_score: float) -> str:
    return (
        f"检索最高相似度 {max_score:.2f} < 阈值 {config.RETRIEVAL_MIN_SIM:.2f}，"
        "本地知识库覆盖不足，已升级云端"
    )


def _local_result(result: dict, text: str) -> dict:
    refused = _is_refusal(text)
    return {
        "route": "local",
        "route_reason": _local_reason(result["max_score"]),
        "model": config.LLM_MODEL,
        "max_score": result["max_score"],
        "min_sim": result["min_sim"],
        "answer": text,
        "refused": refused,
        "grounded": True,
        "sources": [] if refused else _to_sources(result["hits"]),
    }


def _cloud_result(
    result: dict, text: str, reason: str, used_context: bool, error: str | None = None
) -> dict:
    refused = _is_refusal(text)
    return {
        "route": "cloud",
        "route_reason": reason,
        "model": config.DEEPSEEK_MODEL,
        "max_score": result["max_score"],
        "min_sim": result["min_sim"],
        "answer": text,
        "refused": refused,
        "grounded": False,
        "sources": [] if refused or not used_context else _to_sources(result["hits"]),
        **({"cloud_error": error} if error else {}),
    }


def _refusal_result(result: dict, reason: str) -> dict:
    return {
        "route": "local",
        "route_reason": reason,
        "model": config.LLM_MODEL,
        "max_score": result["max_score"],
        "min_sim": result["min_sim"],
        "answer": REFUSAL,
        "refused": True,
        "grounded": True,
        "sources": [],
    }


# ===== 非流式 =====

def answer(query: str, top_k: int | None = None, route_mode: str | None = None) -> dict:
    """非流式问答，供测试、MCP 工具和诊断向导复用。"""
    mode = _mode(route_mode)
    result = kb.search(query, top_k=top_k)
    base = {
        "query": query,
        "route_mode": mode,
        "max_score": result["max_score"],
        "min_sim": result["min_sim"],
    }

    used_context = bool(result["has_relevant"])
    local_text = ""
    if used_context:
        response = _client.chat(
            model=config.LLM_MODEL,
            messages=_messages(query, result["hits"]),
            stream=False,
            keep_alive="30m",
            options=_options(),
        )
        local_text = (response["message"]["content"] or "").strip()
        if not _is_refusal(local_text):
            return {**base, **_local_result(result, local_text)}

    if mode == ROUTE_KB_ONLY:
        reason = (
            _local_reason(result["max_score"])
            if used_context
            else f"检索最高相似度 {result['max_score']:.2f} < 阈值 "
            f"{config.RETRIEVAL_MIN_SIM:.2f}，知识库无相关内容"
        )
        return {**base, **_refusal_result(result, reason)}

    reason = (
        "本地模型判断资料不足，已升级云端复核"
        if used_context
        else _cloud_low_reason(result["max_score"])
    )
    try:
        cloud_text = cloud.complete(_cloud_messages(query, result["hits"], used_context))
    except cloud.CloudUnavailable as exc:
        return {
            **base,
            **_refusal_result(result, f"本地资料不足，且云端升级失败：{exc}"),
            "cloud_error": str(exc),
        }

    if not cloud_text:
        return {
            **base,
            **_refusal_result(result, "云端未返回内容，已回退本地拒答"),
            "cloud_error": "empty cloud response",
        }
    return {**base, **_cloud_result(result, cloud_text, reason, used_context)}


# ===== 流式 =====

def _local_stream(query: str, hits: list[dict]):
    for part in _client.chat(
        model=config.LLM_MODEL,
        messages=_messages(query, hits),
        stream=True,
        keep_alive="30m",
        options=_options(),
    ):
        piece = part["message"]["content"] or ""
        if piece:
            yield piece


def _cloud_stream(messages: list[dict]):
    yield from cloud.stream(messages)


def stream_answer(
    query: str, top_k: int | None = None, route_mode: str | None = None
):
    """逐事件产出问答流，事件字典由路由层序列化为 SSE。

    事件类型：
    - meta   来源列表、初始路由、检索得分（先于正文发送）
    - route  路径切换（本地拒答 / 失败 → 云端），带原因
    - delta  答案增量
    - done   结束，带完整答案、最终路由、是否拒答
    - error  检索或生成异常
    """
    mode = _mode(route_mode)
    try:
        result = kb.search(query, top_k=top_k)
    except Exception as exc:  # 检索阶段失败（如 Ollama 未启动）
        yield {"type": "error", "message": f"检索失败：{exc}"}
        return

    has_relevant = result["has_relevant"]
    sources = _to_sources(result["hits"]) if has_relevant else []

    # 知识库模式，或检索完全没命中且禁止云端：直接拒答
    if not has_relevant and mode == ROUTE_KB_ONLY:
        reason = (
            f"检索最高相似度 {result['max_score']:.2f} < 阈值 "
            f"{config.RETRIEVAL_MIN_SIM:.2f}，知识库无相关内容"
        )
        yield {
            "type": "meta",
            "route": "local",
            "route_reason": reason,
            "model": config.LLM_MODEL,
            "max_score": result["max_score"],
            "min_sim": result["min_sim"],
            "refused": True,
            "grounded": True,
            "sources": [],
        }
        yield {"type": "delta", "content": REFUSAL}
        yield {
            "type": "done",
            "route": "local",
            "route_reason": reason,
            "model": config.LLM_MODEL,
            "answer": REFUSAL,
            "refused": True,
            "grounded": True,
            "sources": [],
        }
        return

    # 检索没命中：智能协同模式直接走云端
    if not has_relevant:
        reason = _cloud_low_reason(result["max_score"])
        yield {
            "type": "meta",
            "route": "cloud",
            "route_reason": reason,
            "model": config.DEEPSEEK_MODEL,
            "max_score": result["max_score"],
            "min_sim": result["min_sim"],
            "refused": False,
            "grounded": False,
            "sources": [],
        }
        collected: list[str] = []
        try:
            for piece in _cloud_stream(_cloud_messages(query, [], False)):
                collected.append(piece)
                yield {"type": "delta", "content": piece}
        except cloud.CloudUnavailable as exc:
            yield {"type": "error", "message": f"云端升级失败：{exc}"}
            return
        text = "".join(collected).strip()
        if not text:
            yield {"type": "error", "message": "云端未返回内容"}
            return
        refused = _is_refusal(text)
        yield {
            "type": "done",
            "route": "cloud",
            "route_reason": reason,
            "model": config.DEEPSEEK_MODEL,
            "answer": text,
            "refused": refused,
            "grounded": False,
            "sources": [],
        }
        return

    # 检索命中：先本地；本地拒答再切换云端
    reason = _local_reason(result["max_score"])
    yield {
        "type": "meta",
        "route": "local",
        "route_reason": reason,
        "model": config.LLM_MODEL,
        "max_score": result["max_score"],
        "min_sim": result["min_sim"],
        "refused": False,
        "grounded": True,
        "sources": sources,
    }

    collected: list[str] = []
    buffer = ""
    decided = False
    emitted = False
    refused = False
    local_error: str | None = None

    try:
        for piece in _local_stream(query, result["hits"]):
            if decided:
                collected.append(piece)
                emitted = True
                yield {"type": "delta", "content": piece}
                continue

            buffer += piece
            stripped = buffer.strip()
            # 还是拒答语的前缀：继续攒，先不发给前端
            if REFUSAL.startswith(stripped) and len(stripped) < len(REFUSAL):
                continue
            if _is_refusal(buffer):
                refused = True
                break
            # 与拒答语分叉，确认是正常答案：把缓冲一次性发出
            decided = True
            collected.append(buffer)
            emitted = True
            yield {"type": "delta", "content": buffer}
            buffer = ""
    except Exception as exc:
        local_error = f"本地模型生成失败：{exc}"

    if not decided and not refused and local_error is None:
        # 流结束但缓冲仍是拒答语前缀：视为拒答 / 空输出
        if _is_refusal(buffer) or (buffer.strip() and REFUSAL.startswith(buffer.strip())):
            refused = True
        elif buffer:
            decided = True
            collected.append(buffer)
            emitted = True
            yield {"type": "delta", "content": buffer}

    if refused or local_error is not None:
        if mode == ROUTE_KB_ONLY:
            if local_error is not None and not emitted:
                yield {"type": "error", "message": local_error}
                return
            text = "".join(collected).strip() if decided else REFUSAL
            yield {
                "type": "done",
                "route": "local",
                "route_reason": reason,
                "model": config.LLM_MODEL,
                "answer": text or REFUSAL,
                "refused": True,
                "grounded": True,
                "sources": [],
            }
            return

        switch_reason = (
            "本地模型判断资料不足，已升级云端复核"
            if refused
            else "本地模型生成失败，已升级云端"
        )
        if emitted:
            # 已经吐出一部分正文，不能再无损切换到云端
            yield {"type": "error", "message": local_error or "本地模型中途中断"}
            return

        yield {
            "type": "route",
            "route": "cloud",
            "route_reason": switch_reason,
            "model": config.DEEPSEEK_MODEL,
            "grounded": False,
            "sources": sources,
        }
        collected = []
        try:
            for piece in _cloud_stream(
                _cloud_messages(query, result["hits"], True)
            ):
                collected.append(piece)
                yield {"type": "delta", "content": piece}
        except cloud.CloudUnavailable as exc:
            yield {"type": "error", "message": f"云端升级失败：{exc}"}
            return
        text = "".join(collected).strip()
        if not text:
            yield {"type": "error", "message": "云端未返回内容"}
            return
        cloud_refused = _is_refusal(text)
        yield {
            "type": "done",
            "route": "cloud",
            "route_reason": switch_reason,
            "model": config.DEEPSEEK_MODEL,
            "answer": text,
            "refused": cloud_refused,
            "grounded": False,
            "sources": [] if cloud_refused else sources,
        }
        return

    text = "".join(collected).strip()
    yield {
        "type": "done",
        "route": "local",
        "route_reason": reason,
        "model": config.LLM_MODEL,
        "answer": text,
        "refused": False,
        "grounded": True,
        "sources": sources,
    }


def sse(event: dict) -> str:
    """把事件字典编码为 SSE 数据帧。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
