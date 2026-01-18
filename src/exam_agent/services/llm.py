from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.modelscope import create_chat_completion, stream_chat_completion


async def create_completion(
    messages: list[dict[str, Any]],
    *,
    temperature: float | None = None,
    top_p: float | None = None,
    stream: bool = False,
) -> dict[str, Any]:
    return await create_chat_completion(
        messages,
        model=settings.model_default,
        temperature=temperature,
        top_p=top_p,
        presence_penalty=settings.model_presence_penalty_default,
        frequency_penalty=settings.model_frequency_penalty_default,
        max_tokens=settings.model_max_tokens_default,
        stream=stream,
    )


async def stream_completion(messages: list[dict[str, Any]]):
    return await stream_chat_completion(
        messages,
        model=settings.model_default,
        temperature=settings.model_temperature_default,
        top_p=settings.model_top_p_default,
        presence_penalty=settings.model_presence_penalty_default,
        frequency_penalty=settings.model_frequency_penalty_default,
        max_tokens=settings.model_max_tokens_default,
        stream=True,
    )
