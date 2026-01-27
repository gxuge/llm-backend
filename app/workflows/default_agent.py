from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from app.core.config import settings
from app.services.modelscope import stream_chat_completion
from app.services.run_store import _sse_event


def _build_messages(input_text: str, messages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if messages:
        return messages
    return [{"role": "user", "content": input_text}]


async def stream_default_agent(
    *,
    input_text: str,
    messages: list[dict[str, Any]] | None = None,
    model: str | None = None,
    sampling: dict[str, Any] | None = None,
) -> AsyncGenerator[str, None]:
    payload_messages = _build_messages(input_text, messages)
    model_name = model or settings.model_default
    sampling = sampling or {}

    stream = await stream_chat_completion(
        payload_messages,
        model_name,
        temperature=sampling.get("temperature", settings.model_temperature_default),
        top_p=sampling.get("top_p", settings.model_top_p_default),
        presence_penalty=sampling.get("presence_penalty", settings.model_presence_penalty_default),
        frequency_penalty=sampling.get("frequency_penalty", settings.model_frequency_penalty_default),
        max_tokens=sampling.get("max_tokens", settings.model_max_tokens_default),
        stream=True,
    )

    text_buffer = ""
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    think_started = False
    done = False

    async for chunk in stream:
        part = chunk.decode("utf-8", errors="ignore")
        text_buffer += part
        while "\n\n" in text_buffer:
            block, text_buffer = text_buffer.split("\n\n", 1)
            for line in block.splitlines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if not data:
                    continue
                if data == "[DONE]":
                    done = True
                    break
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                content = payload.get("content") or ""
                reasoning = payload.get("reasoning_content") or ""
                if content:
                    content_parts.append(content)
                    yield _sse_event("summary.delta", {"delta": content})
                if reasoning:
                    if not think_started:
                        think_started = True
                        yield _sse_event("summary.think.start", {})
                    reasoning_parts.append(reasoning)
                    yield _sse_event("summary.think.delta", {"delta": reasoning})
            if done:
                break
        if done:
            break

    if think_started:
        yield _sse_event("summary.think.end", {})
    answer = "".join(content_parts)
    reasoning_text = "".join(reasoning_parts)
    end_payload: dict[str, Any] = {"answer": answer}
    if reasoning_text:
        end_payload["reasoning"] = reasoning_text
    yield _sse_event("summary.end", end_payload)
    yield _sse_event("run.end", {"status": "ok"})
