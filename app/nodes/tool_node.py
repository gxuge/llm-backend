from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from app.nodes.state import AgentState
from app.nodes.utils import merge_tool_data
from app.tools import SCHOOL_TOOLS
from app.tools.school_tools import set_access_token
from app.tools.exam_agent_tools import compute_recommendations
from src.exam_agent.services.events import emit_event


TOOL_LIST = [*SCHOOL_TOOLS, compute_recommendations]
TOOL_MAP = {tool.name: tool for tool in TOOL_LIST}


async def tool_node(state: AgentState) -> AgentState:
    """执行工具调用并汇总结果，输出 tool.* 事件。"""
    last_ai = next(
        (msg for msg in reversed(state.get("messages", [])) if isinstance(msg, AIMessage)),
        None,
    )
    if not last_ai or not last_ai.tool_calls:
        return {}

    results: list[ToolMessage] = []
    tool_data = state.get("tool_data", {})
    tool_errors = list(state.get("tool_errors", []))
    computed: dict[str, Any] | None = None
    group_id = state.get("tool_group_id") or uuid.uuid4().hex

    token = state.get("access_token")
    if token:
        set_access_token(token)

    async def _run_tool(call: dict[str, Any]) -> tuple[str, Any, str]:
        # 单工具调用封装，兼容 async/sync 工具
        tool = TOOL_MAP.get(call["name"])
        if not tool:
            return call["name"], {"error": "Tool not found."}, call["id"]
        try:
            if hasattr(tool, "ainvoke"):
                payload = await tool.ainvoke(call["args"])
            else:
                payload = await tool.invoke(call["args"])
            return call["name"], payload, call["id"]
        except Exception as exc:  # pragma: no cover - tool failures
            return call["name"], {"error": str(exc)}, call["id"]

    tasks = [_run_tool(call) for call in last_ai.tool_calls]
    for name, payload, call_id in await asyncio.gather(*tasks):
        result_summary = None
        if isinstance(payload, dict):
            result_summary = payload.get("summary") or payload.get("message")
        if result_summary is None:
            text = str(payload)
            result_summary = text[:200]
        if isinstance(payload, dict) and payload.get("error"):
            tool_errors.append(f"{name}: {payload['error']}")
            emit_event(
                state,
                "tool.error",
                {
                    "toolCallId": call_id,
                    "apiName": name,
                    "message": payload["error"],
                },
                status="failed",
                step_id=call_id,
                group_id=group_id,
            )
        else:
            emit_event(
                state,
                "tool.result",
                {
                    "toolCallId": call_id,
                    "apiName": name,
                    "ok": True,
                    "resultSummary": result_summary,
                },
                status="succeeded",
                step_id=call_id,
                group_id=group_id,
            )
        if name == "compute_recommendations" and isinstance(payload, dict):
            computed = payload
        else:
            tool_data = merge_tool_data(tool_data, name, payload)
        results.append(
            ToolMessage(
                content=json.dumps(payload, ensure_ascii=False),
                tool_call_id=call_id,
            )
        )

    updates: dict[str, Any] = {
        "messages": results,
        "tool_data": tool_data,
        "tool_errors": tool_errors,
        "tool_group_id": group_id,
    }
    if computed is not None:
        updates["computed"] = computed
    if token:
        set_access_token(None)
    return updates
