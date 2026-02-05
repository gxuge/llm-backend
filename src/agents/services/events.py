from __future__ import annotations

import time
import uuid
from typing import Any

from langgraph.config import get_stream_writer

from src.agents.schemas.state import AgentState


def _get_writer(state: AgentState):
    if state.get("writer"):
        return state["writer"]
    try:
        return get_stream_writer()
    except RuntimeError:
        return None


def _ensure_run_id(state: AgentState) -> str:
    run_id = state.get("run_id")
    if not run_id:
        run_id = uuid.uuid4().hex
        state["run_id"] = run_id
    return run_id


def _next_sequence(state: AgentState) -> int:
    seq = int(state.get("sequence_number") or 0) + 1
    state["sequence_number"] = seq
    return seq


def emit_event(
    state: AgentState,
    event: str,
    data: dict[str, Any] | None = None,
    *,
    step_id: str | None = None,
    parent_id: str | None = None,
    status: str | None = None,
    group_id: str | None = None,
) -> None:
    writer = _get_writer(state)
    if not writer:
        return
    payload: dict[str, Any] = {
        "v": 1,
        "run_id": _ensure_run_id(state),
        "ts": int(time.time() * 1000),
        "sequence_number": _next_sequence(state),
    }
    if step_id:
        payload["step_id"] = step_id
    if parent_id:
        payload["parent_id"] = parent_id
    if status:
        payload["status"] = status
    if group_id:
        payload["group_id"] = group_id
    if data:
        payload.update(data)
    writer({"event": event, "data": payload})
