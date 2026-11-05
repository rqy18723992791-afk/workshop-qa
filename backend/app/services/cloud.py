"""DeepSeek 云端兜底客户端（OpenAI 兼容接口）。

只在两种情况下被调用：
1. 检索相似度低于阈值（本地知识库覆盖不到）；
2. 本地模型明确拒答（资料不足）。

密钥只从 backend/.env 读取，代码与日志中不出现明文。
"""
import json
from collections.abc import Iterator

import httpx

from .. import config


class CloudUnavailable(RuntimeError):
    """云端未配置或调用失败，调用方据此回退到本地拒答。"""


def is_configured() -> bool:
    return bool(config.DEEPSEEK_API_KEY)


def _payload(messages: list[dict], stream: bool) -> dict:
    return {
        "model": config.DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.2,  # 车间场景要稳定，不要创造性
        "stream": stream,
    }


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }


def _url() -> str:
    return f"{config.DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"


def complete(messages: list[dict]) -> str:
    """非流式调用，返回完整文本。"""
    if not is_configured():
        raise CloudUnavailable("未配置 DEEPSEEK_API_KEY")
    try:
        with httpx.Client(timeout=config.CLOUD_TIMEOUT) as client:
            resp = client.post(_url(), headers=_headers(), json=_payload(messages, False))
            resp.raise_for_status()
            data = resp.json()
        return (data["choices"][0]["message"]["content"] or "").strip()
    except CloudUnavailable:
        raise
    except Exception as exc:
        raise CloudUnavailable(f"云端模型调用失败：{type(exc).__name__}") from exc


def stream(messages: list[dict]) -> Iterator[str]:
    """流式调用，逐段产出文本增量。"""
    if not is_configured():
        raise CloudUnavailable("未配置 DEEPSEEK_API_KEY")
    try:
        with httpx.Client(timeout=config.CLOUD_TIMEOUT) as client:
            with client.stream(
                "POST", _url(), headers=_headers(), json=_payload(messages, True)
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        piece = obj["choices"][0]["delta"].get("content") or ""
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if piece:
                        yield piece
    except CloudUnavailable:
        raise
    except Exception as exc:
        raise CloudUnavailable(f"云端模型调用失败：{type(exc).__name__}") from exc
