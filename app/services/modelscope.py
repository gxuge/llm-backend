# ??????????????????
import json
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelscopeChatError(Exception):
    """Raised when the ModelScope chat API returns an error or malformed payload."""


async def create_chat_completion(
    messages: list[dict[str, Any]],
    model: str,
    *,
    api_key: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    presence_penalty: float | None = None,
    frequency_penalty: float | None = None,
    max_tokens: int | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    """
    统一的非流式对话接口：返回 content/reasoning/model/raw。
    """
    url = f"{settings.modelscope_api_base.rstrip('/')}/chat/completions"
    auth_key = api_key or settings.modelscope_api_key
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_key}",
    }
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}

    optional_fields = {
        "temperature": temperature,
        "top_p": top_p,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "max_tokens": max_tokens,
    }
    for key, value in optional_fields.items():
        if value is not None:
            payload[key] = value

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise ModelscopeChatError(
            f"ModelScope responded with {response.status_code}: {response.text}"
        )

    try:
        data = response.json()
    except json.JSONDecodeError as exc:  # pragma: no cover - safety guard
        raise ModelscopeChatError(f"ModelScope response is not JSON: {exc}") from exc

    choices = data.get("choices") or []
    first_choice = choices[0] if choices else {}
    message_block = first_choice.get("message") or {}
    content = message_block.get("content", "")
    reasoning = (
        message_block.get("reasoning_content")
        or first_choice.get("reasoning")
        or data.get("reasoning_content")
    )

    if not content:
        raise ModelscopeChatError("ModelScope response missing `message.content`.")

    return {"content": content, "reasoning": reasoning, "model": model, "raw": data}


async def stream_chat_completion(
    messages: list[dict[str, Any]],
    model: str,
    *,
    api_key: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    presence_penalty: float | None = None,
    frequency_penalty: float | None = None,
    max_tokens: int | None = None,
    stream: bool = True,
):
    """
    流式对话接口：返回上游 SSE 字节流。
    """
    url = f"{settings.modelscope_api_base.rstrip('/')}/chat/completions"
    auth_key = api_key or settings.modelscope_api_key
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_key}",
    }
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}

    optional_fields = {
        "temperature": temperature,
        "top_p": top_p,
        "presence_penalty": presence_penalty,
        "frequency_penalty": frequency_penalty,
        "max_tokens": max_tokens,
    }
    for key, value in optional_fields.items():
        if value is not None:
            payload[key] = value

    # 统一包装错误事件，保持前端 SSE 协议一致
    def _error_event(message: str, status_code: int | None = None) -> bytes:
        data: dict[str, Any] = {"error": message}
        if status_code is not None:
            data["status_code"] = status_code
        return (
            f"event: error\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode(
                "utf-8"
            )
        )

    async def _gen():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code >= 400:
                        text = await response.aread()
                        message = text.decode(errors="ignore").strip()
                        yield _error_event(
                            f"ModelScope responded with {response.status_code}: {message}",
                            response.status_code,
                        )
                        yield b"data: [DONE]\n\n"
                        return
                    buffer = ""
                    async for chunk in response.aiter_text():
                        if not chunk:
                            continue
                        buffer += chunk
                        while "\n\n" in buffer:
                            raw_event, buffer = buffer.split("\n\n", 1)
                            for line in raw_event.splitlines():
                                if not line.startswith("data:"):
                                    continue
                                data = line[len("data:") :].strip()
                                if not data:
                                    continue
                                if data == "[DONE]":
                                    yield b"data: [DONE]\n\n"
                                    return
                                try:
                                    payload_json = json.loads(data)
                                except json.JSONDecodeError:
                                    continue
                                choices = payload_json.get("choices") or []
                                choice = choices[0] if choices else {}
                                delta = choice.get("delta") or {}
                                message = choice.get("message") or {}
                                content = (
                                    payload_json.get("content")
                                    or delta.get("content")
                                    or message.get("content")
                                    or ""
                                )
                                reasoning = (
                                    payload_json.get("reasoning_content")
                                    or delta.get("reasoning_content")
                                    or message.get("reasoning_content")
                                    or ""
                                )
                                if not content and not reasoning:
                                    continue
                                compact: dict[str, Any] = {}
                                if content:
                                    compact["content"] = content
                                if reasoning:
                                    compact["reasoning_content"] = reasoning
                                yield (
                                    f"data: {json.dumps(compact, ensure_ascii=False)}\n\n".encode(
                                        "utf-8"
                                    )
                                )
        except ModelscopeChatError as exc:
            yield _error_event(str(exc))
            yield b"data: [DONE]\n\n"
        except Exception:  # pragma: no cover - unexpected stream errors
            logger.exception("Unhandled ModelScope stream error")
            yield _error_event("Unexpected chat proxy error")
            yield b"data: [DONE]\n\n"

    return _gen()
