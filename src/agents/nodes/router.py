from __future__ import annotations

import json
import re
from typing import Any

from src.app.core.config import settings
from src.app.core.langfuse import end_span, get_current_trace, start_span
from src.app.services.modelscope import create_chat_completion
from src.agents.nodes.state import AgentState, INTENT_OPTIONS
from src.agents.services.events import emit_event
from src.agents.tools import SCHOOL_TOOLS, SCHOOL_TOOL_SCHEMAS


def _tool_gate_llm_options() -> dict[str, Any]:
    model = (settings.tool_gate_model or "").strip() or settings.model_default
    return {
        "model": model,
        "temperature": settings.tool_gate_temperature,
        "top_p": settings.tool_gate_top_p,
        "stream": False,
    }


def _rule_need_tools(query: Any) -> bool:
    if not query:
        return False
    # 规则门控：第一个意图是“政策”类，通常不需要外部工具。
    return query.intent in set(INTENT_OPTIONS[1:])


async def _llm_need_tools(state: AgentState, *, need_tools_rule: bool) -> tuple[bool | None, str]:
    # 没有模型密钥时直接返回 None，让上层走规则兜底。
    if not settings.modelscope_api_key:
        return None, "missing_modelscope_api_key"

    query = state.get("query")
    prompt = (
        "你是工具门控分类器。"
        "只能返回 JSON：{\"need_tools\": true|false}。"
        "当问题需要从学校 API 获取事实数据或进行计算时，返回 true。"
        "当问题只需政策解释或直接对话回复时，返回 false。"
    )
    payload = {
        "question": state.get("question", ""),
        "intent": query.intent if query else None,
        "score": query.score if query else None,
        "school_name": query.school_name if query else None,
        "area_name": query.area_name if query else None,
        "rule_need_tools": need_tools_rule,
    }

    try:
        result = await create_chat_completion(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            **_tool_gate_llm_options(),
        )
        match = re.search(r"\{.*\}", result.get("content", ""), re.DOTALL)
        if not match:
            return None, "no_json"
        parsed = json.loads(match.group(0))
        if "need_tools" not in parsed:
            return None, "missing_need_tools_field"
        return bool(parsed.get("need_tools")), "ok"
    except Exception:
        return None, "llm_error"


def _build_school_tool_schemas() -> list[dict[str, Any]]:
    if SCHOOL_TOOL_SCHEMAS:
        return SCHOOL_TOOL_SCHEMAS

    schemas: list[dict[str, Any]] = []
    for tool in SCHOOL_TOOLS:
        parameters = {
            "type": "object",
            "properties": tool.args or {},
            "additionalProperties": False,
        }
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": parameters,
                },
            }
        )
    return schemas


def _parse_tool_call_suggestions(raw_tool_calls: list[Any]) -> list[dict[str, Any]]:
    parsed_calls: list[dict[str, Any]] = []
    for item in raw_tool_calls:
        if not isinstance(item, dict):
            continue
        function_block = item.get("function")
        if not isinstance(function_block, dict):
            continue
        name = function_block.get("name")
        if not isinstance(name, str) or not name:
            continue
        arguments_raw = function_block.get("arguments")
        args: dict[str, Any] = {}
        if isinstance(arguments_raw, str) and arguments_raw.strip():
            try:
                loaded = json.loads(arguments_raw)
                if isinstance(loaded, dict):
                    args = loaded
            except Exception:
                args = {}
        elif isinstance(arguments_raw, dict):
            args = arguments_raw
        parsed_calls.append(
            {
                "id": item.get("id") or f"llm_{name}",
                "name": name,
                "args": args,
            }
        )
    return parsed_calls


async def _llm_need_tools_tool_call(
    state: AgentState, *, need_tools_rule: bool
) -> tuple[bool | None, str, list[dict[str, Any]]]:
    # 没有模型密钥时直接返回 None，让上层走规则兜底。
    if not settings.modelscope_api_key:
        return None, "missing_modelscope_api_key", []

    query = state.get("query")
    prompt = "你是工具规划器。根据用户问题，从提供的学校工具中选择需要调用的工具并给出参数。"
    payload = {
        "question": state.get("question", ""),
        "intent": query.intent if query else None,
        "score": query.score if query else None,
        "school_name": query.school_name if query else None,
        "area_name": query.area_name if query else None,
        "rule_need_tools": need_tools_rule,
    }
    tools = _build_school_tool_schemas()

    try:
        result = await create_chat_completion(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            tools=tools,
            tool_choice="auto",
            **_tool_gate_llm_options(),
        )
        tool_calls = result.get("tool_calls") or []
        parsed_calls = _parse_tool_call_suggestions(tool_calls)
        if not parsed_calls:
            return False, "no_tool_calls", []
        return True, "ok", parsed_calls
    except Exception:
        return None, "tool_call_error", []


async def route_tools(state: AgentState) -> AgentState:
    query = state.get("query")
    intent = query.intent if query else INTENT_OPTIONS[0]
    trace = get_current_trace()
    span = start_span(trace, name="node.route_tools", input_data={"intent": intent})

    # 第一层：规则判定是否需要工具。
    need_tools_rule = _rule_need_tools(query)
    mode = (settings.tool_planner_mode).strip().lower()
    if mode not in {"rule", "llm", "hybrid", "tool_call"}:
        mode = "hybrid"

    need_tools_llm: bool | None = None
    need_tools_tool_call: bool | None = None
    suggested_tool_calls: list[dict[str, Any]] = []
    llm_reason = "not_called"
    if mode in {"llm", "hybrid"}:
        # 第二层：LLM 门控（仅决定“要不要工具”）。
        need_tools_llm, llm_reason = await _llm_need_tools(state, need_tools_rule=need_tools_rule)
    elif mode == "tool_call":
        # 原生函数调用门控：通过 tool_call 返回 need_tools。
        need_tools_tool_call, llm_reason, suggested_tool_calls = await _llm_need_tools_tool_call(
            state, need_tools_rule=need_tools_rule
        )

    if mode == "rule":
        need_tools = need_tools_rule
        decision_source = "rule"
    elif mode == "tool_call":
        if need_tools_tool_call is None:
            # tool_call 失败时回退到规则结果，保证稳定性。
            need_tools = need_tools_rule
            decision_source = "rule_fallback"
        else:
            need_tools = need_tools_tool_call
            decision_source = "tool_call"
    else:
        if need_tools_llm is None:
            # LLM 失败或不可用时回退到规则结果，保证稳定性。
            need_tools = need_tools_rule
            decision_source = "rule_fallback"
        else:
            need_tools = need_tools_llm
            decision_source = "llm"

    if need_tools and query and query.registered_residence_type is None:
        # 工具分支默认补齐户籍类型，避免后续工具参数为空。
        query.registered_residence_type = 2

    recommend_intents = {INTENT_OPTIONS[3], INTENT_OPTIONS[5]}
    need_compute_rule = bool(query and query.score is not None and query.intent in recommend_intents)

    emit_event(
        state,
        "trace.event",
        {
            "intent": intent,
            "need_tools": need_tools,
            "need_tools_rule": need_tools_rule,
            "need_tools_llm": need_tools_llm,
            "need_tools_tool_call": need_tools_tool_call,
            "suggested_tool_calls": suggested_tool_calls,
            "tool_planner_mode": mode,
            "decision_source": decision_source,
            "llm_reason": llm_reason,
        },
        status="running",
    )
    end_span(
        span,
        output={
            "need_tools": need_tools,
            "need_tools_rule": need_tools_rule,
            "need_tools_llm": need_tools_llm,
            "need_tools_tool_call": need_tools_tool_call,
            "suggested_tool_calls": len(suggested_tool_calls),
            "tool_planner_mode": mode,
            "decision_source": decision_source,
            "need_compute_rule": need_compute_rule,
        },
    )
    return {
        "need_tools": need_tools,
        "need_tools_rule": need_tools_rule,
        "need_tools_llm": need_tools_llm,
        "need_tools_tool_call": need_tools_tool_call,
        "suggested_tool_calls": suggested_tool_calls,
        "query": query,
        "need_compute_rule": need_compute_rule,
    }
