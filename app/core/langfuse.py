from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from app.core.config import settings

try:
    from langfuse import Langfuse
except Exception:  # pragma: no cover - optional dependency
    Langfuse = None

_client: Langfuse | None = None
_current_trace: ContextVar[Any | None] = ContextVar("langfuse_trace", default=None)


def get_langfuse() -> Langfuse | None:
    if not settings.langfuse_enabled:
        return None
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    global _client
    if _client is None and Langfuse is not None:
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_base_url or None,
        )
    return _client


def set_current_trace(trace: Any | None) -> None:
    _current_trace.set(trace)


def get_current_trace() -> Any | None:
    return _current_trace.get()


def start_trace(
    *,
    trace_id: str,
    session_id: str | None,
    user_id: str | None,
    name: str,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    langfuse = get_langfuse()
    if not langfuse:
        return None
    try:
        trace = langfuse.trace(
            id=trace_id,
            name=name,
            session_id=session_id,
            user_id=user_id,
            metadata=metadata or {},
        )
    except Exception:
        return None
    set_current_trace(trace)
    return trace


def flush_langfuse() -> None:
    langfuse = get_langfuse()
    if not langfuse:
        return
    try:
        langfuse.flush()
    except Exception:
        return


def start_generation(
    trace: Any | None,
    *,
    name: str,
    model: str,
    input_data: Any,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    if trace is None:
        return None
    try:
        return trace.generation(
            name=name,
            model=model,
            input=input_data,
            metadata=metadata or {},
        )
    except Exception:
        return None


def end_generation(generation: Any | None, *, output: Any, metadata: dict[str, Any] | None = None) -> None:
    if generation is None:
        return
    try:
        generation.end(output=output, metadata=metadata or {})
    except Exception:
        return


def start_span(
    trace: Any | None,
    *,
    name: str,
    input_data: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    if trace is None:
        return None
    try:
        return trace.span(name=name, input=input_data, metadata=metadata or {})
    except Exception:
        return None


def end_span(span: Any | None, *, output: Any | None = None, metadata: dict[str, Any] | None = None) -> None:
    if span is None:
        return
    try:
        span.end(output=output, metadata=metadata or {})
    except Exception:
        return
