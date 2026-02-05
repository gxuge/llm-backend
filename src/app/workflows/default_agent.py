from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from src.app.core.config import settings
from src.agents.nodes.llm_stream_node import stream_llm_sse
from src.app.services.run_store import _sse_event


def _build_messages(input_text: str, messages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if messages:
        return messages
    return [{"role": "user", "content": input_text}]


def _extract_enable_think(sampling: dict[str, Any] | None) -> bool:
    if not sampling:
        return False
    return bool(sampling.get("enable_think") or sampling.get("enableThink"))


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

    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    enable_think = _extract_enable_think(sampling)
    show_think = enable_think
    async for chunk in stream_llm_sse(
        messages=payload_messages,
        model=model_name,
        sampling=sampling,
        enable_think=enable_think,
        show_think=show_think,
        event_prefix="summary",
        content_parts=content_parts,
        reasoning_parts=reasoning_parts,
    ):
        yield chunk
    answer = "".join(content_parts)
    reasoning_text = "".join(reasoning_parts)
    end_payload: dict[str, Any] = {"answer": answer}
    if reasoning_text:
        end_payload["reasoning"] = reasoning_text
    yield _sse_event("summary.end", end_payload)
