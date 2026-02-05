from __future__ import annotations

import json
import re

from langchain_core.messages import AIMessage

from src.app.core.config import settings
from src.app.core.langfuse import end_span, get_current_trace, start_span
from src.app.prompts.exam_agent import compute_decider_system_prompt
from src.app.services.modelscope import create_chat_completion
from src.agents.nodes.state import AgentState
from src.agents.services.events import emit_event


async def compute_decider(state: AgentState) -> AgentState:
    """判断是否需要计算类工具，并输出 tool.call。"""
    query = state.get("query")
    tool_data = state.get("tool_data", {})
    trace = get_current_trace()
    span = start_span(trace, name="node.compute_decider", input_data={"has_tool_data": bool(tool_data)})
    if not tool_data:
        need_compute_rule = bool(state.get("need_compute_rule"))
        if not need_compute_rule:
            end_span(span, output={"need_compute": False, "reason": "no_tool_data"})
            return {
                "need_compute_llm": False,
                "need_compute": False,
                "messages": [AIMessage(content="无需计算", tool_calls=[])],
            }
        args = {"query": query.model_dump() if query else None, "tool_data": {}}
        call_id = "call_compute_recommendations"
        emit_event(
            state,
            "tool.call",
            {"toolCallId": call_id, "apiName": "compute_recommendations", "arguments": args},
            status="queued",
            step_id=call_id,
            group_id="compute",
        )
        ai_message = AIMessage(
            content="执行计算工具",
            tool_calls=[{"id": call_id, "name": "compute_recommendations", "args": args}],
        )
        end_span(span, output={"need_compute": True, "path": "rule_only"})
        return {
            "need_compute_llm": False,
            "need_compute": True,
            "tool_group_id": "compute",
            "messages": [ai_message],
        }

    system_prompt = compute_decider_system_prompt()
    payload = {
        "question": state.get("question", ""),
        "intent": query.intent if query else "政策",
        "score": query.score if query else None,
        "has_score_tools": bool(tool_data.get("list_school_scores")),
    }
    try:
        result = await create_chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            model=settings.model_default,
            temperature=0,
            top_p=1,
            stream=False,
        )
        match = re.search(r"\{.*\}", result["content"], re.DOTALL)
        if not match:
            raise ValueError("No JSON in response.")
        parsed = json.loads(match.group(0))
        need_compute_llm = bool(parsed.get("need_compute"))
    except Exception:
        need_compute_llm = False
        emit_event(
            state,
            "trace.event",
            {"message": "Compute 判断失败，已降级为规则判断。"},
            status="running",
        )

    need_compute_rule = bool(state.get("need_compute_rule"))
    need_compute = need_compute_rule or need_compute_llm
    if not need_compute:
        end_span(span, output={"need_compute": False, "need_compute_llm": need_compute_llm})
        return {
            "need_compute_llm": need_compute_llm,
            "need_compute": False,
            "messages": [AIMessage(content="无需计算", tool_calls=[])],
        }

    args = {
        "query": query.model_dump() if query else None,
        "tool_data": tool_data,
    }
    call_id = "call_compute_recommendations"
    emit_event(
        state,
        "tool.call",
        {"toolCallId": call_id, "apiName": "compute_recommendations", "arguments": args},
        status="queued",
        step_id=call_id,
        group_id="compute",
    )
    ai_message = AIMessage(
        content="执行计算工具",
        tool_calls=[{"id": call_id, "name": "compute_recommendations", "args": args}],
    )
    end_span(span, output={"need_compute": True, "need_compute_llm": need_compute_llm})
    return {
        "need_compute_llm": need_compute_llm,
        "need_compute": True,
        "tool_group_id": "compute",
        "messages": [ai_message],
    }
