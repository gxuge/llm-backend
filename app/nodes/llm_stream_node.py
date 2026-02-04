from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.core.langfuse import end_span, get_current_trace, start_span
from app.nodes.state import AgentState
from app.nodes.utils import build_context_block
from app.prompts.exam_agent import (
    final_synth_system_prompt,
    pre_synth_system_prompt,
    rag_summary_system_prompt,
    tool_summary_system_prompt,
)
from app.services.modelscope import stream_chat_completion
from app.services.run_store import _sse_event
from src.exam_agent.services.events import emit_event


def _sampling_value(sampling: dict[str, Any] | None, key: str, default: Any) -> Any:
    if not sampling:
        return default
    return sampling.get(key, default)


def _extract_enable_think(state: AgentState) -> bool:
    value = state.get("enable_think")
    return bool(value) if value is not None else False


def _extract_show_think(state: AgentState) -> bool:
    value = state.get("show_think")
    return bool(value) if value is not None else False


async def _stream_llm(
    state: AgentState,
    messages: list[dict[str, Any]],
    event_name: str,
    *,
    step_id: str,
    parent_id: str | None = None,
    think_event_name: str | None = None,
    think_start_event: str | None = None,
    think_end_event: str | None = None,
    think_step_id: str | None = None,
    emit_content_events: bool = True,
    enable_think: bool = False,
    show_think: bool = False,
) -> str:
    buffer_text: list[str] = []
    think_started = False
    stream = await stream_chat_completion(
        messages,
        model=settings.model_default,
        temperature=settings.model_temperature_default,
        top_p=settings.model_top_p_default,
        presence_penalty=settings.model_presence_penalty_default,
        frequency_penalty=settings.model_frequency_penalty_default,
        max_tokens=settings.model_max_tokens_default,
        stream=True,
    )
    text_buffer = ""
    async for chunk in stream:
        part = chunk.decode("utf-8", errors="ignore")
        text_buffer += part
        while "\n\n" in text_buffer:
            block, text_buffer = text_buffer.split("\n\n", 1)
            is_error = any(line.startswith("event: error") for line in block.splitlines())
            for line in block.splitlines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    return "".join(buffer_text)
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if is_error and payload.get("error"):
                    emit_event(
                        state,
                        f"{event_name.split('.')[0]}.error",
                        {"message": payload["error"]},
                        status="failed",
                        step_id=step_id,
                        parent_id=parent_id,
                    )
                    return "".join(buffer_text)
                content = payload.get("content") or ""
                if content:
                    buffer_text.append(content)
                    if emit_content_events:
                        emit_event(
                            state,
                            event_name,
                            {"text": content},
                            status="running",
                            step_id=step_id,
                            parent_id=parent_id,
                        )
                reasoning = payload.get("reasoning_content") or ""
                if reasoning and enable_think and think_event_name and show_think:
                    if think_start_event and not think_started:
                        emit_event(
                            state,
                            think_start_event,
                            {"stage": "think"},
                            status="running",
                            step_id=think_step_id or step_id,
                            parent_id=parent_id,
                        )
                        think_started = True
                    emit_event(
                        state,
                        think_event_name,
                        {"text": reasoning},
                        status="running",
                        step_id=think_step_id or step_id,
                        parent_id=parent_id,
                    )
    if think_started and think_end_event:
        emit_event(
            state,
            think_end_event,
            {"stage": "think"},
            status="succeeded",
            step_id=think_step_id or step_id,
            parent_id=parent_id,
        )
    return "".join(buffer_text)


async def stream_llm_sse(
    *,
    messages: list[dict[str, Any]],
    model: str,
    sampling: dict[str, Any] | None,
    enable_think: bool,
    show_think: bool,
    event_prefix: str,
    content_parts: list[str],
    reasoning_parts: list[str],
):
    stream = await stream_chat_completion(
        messages,
        model=model,
        temperature=_sampling_value(sampling, "temperature", settings.model_temperature_default),
        top_p=_sampling_value(sampling, "top_p", settings.model_top_p_default),
        presence_penalty=_sampling_value(sampling, "presence_penalty", settings.model_presence_penalty_default),
        frequency_penalty=_sampling_value(sampling, "frequency_penalty", settings.model_frequency_penalty_default),
        max_tokens=_sampling_value(sampling, "max_tokens", settings.model_max_tokens_default),
        stream=True,
    )

    text_buffer = ""
    think_started = False

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
                    return
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                content = payload.get("content") or ""
                reasoning = payload.get("reasoning_content") or ""
                if content:
                    content_parts.append(content)
                    yield _sse_event(f"{event_prefix}.delta", {"text": content})
                if reasoning and enable_think and show_think:
                    if not think_started:
                        think_started = True
                        yield _sse_event(f"{event_prefix}.think.start", {})
                    reasoning_parts.append(reasoning)
                    yield _sse_event(f"{event_prefix}.think.delta", {"text": reasoning})

    if think_started and enable_think and show_think:
        yield _sse_event(f"{event_prefix}.think.end", {})


async def pre_synth(state: AgentState) -> AgentState:
    context_block = build_context_block(state.get("policy_context", []))
    trace = get_current_trace()
    span = start_span(trace, name="node.pre_synth", input_data={"context_count": len(state.get("policy_context", []))})
    emit_event(state, "summary.start", {"stage": "rag"}, status="running", step_id="summary.rag")
    prompt = [
        {"role": "system", "content": pre_synth_system_prompt()},
        {"role": "user", "content": f"Question: {state['question']}\nContext:\n{context_block}"},
    ]
    await _stream_llm(state, prompt, "summary.delta", step_id="summary.rag")
    emit_event(state, "summary.end", {"stage": "rag"}, status="succeeded", step_id="summary.rag")
    end_span(span, output={"stage": "rag"})
    return {}


async def rag_summary(state: AgentState) -> AgentState:
    """基于 RAG 上下文输出独立摘要流。"""
    context_block = build_context_block(state.get("policy_context", []))
    trace = get_current_trace()
    span = start_span(trace, name="node.rag_summary", input_data={"context_count": len(state.get("policy_context", []))})
    emit_event(state, "rag.summary.start", {"stage": "rag"}, status="running", step_id="rag.summary")
    prompt = [
        {"role": "system", "content": rag_summary_system_prompt()},
        {"role": "user", "content": f"问题：{state['question']}\n政策片段：\n{context_block}"},
    ]
    enable_think = _extract_enable_think(state)
    show_think = False
    await _stream_llm(
        state,
        prompt,
        "rag.summary.delta",
        step_id="rag.summary",
        enable_think=enable_think,
        show_think=show_think,
    )
    emit_event(state, "rag.summary.end", {"stage": "rag"}, status="succeeded", step_id="rag.summary")
    emit_event(
        state,
        "rag.end",
        {"context_count": len(state.get("policy_context", []))},
        status="succeeded",
        step_id="rag",
    )
    end_span(span, output={"stage": "rag"})
    return {}


def _sanitize_tool_data(tool_data: dict[str, Any], computed: dict[str, Any]) -> dict[str, Any]:
    safe_payload: dict[str, Any] = {"tools": {}}
    tool_whitelist: dict[str, set[str]] = {
        "list_school_page": {
            "id",
            "schoolId",
            "name",
            "schoolName",
            "areaId",
            "areaName",
            "schoolType",
            "boardingType",
        },
        "list_area_page": {"id", "areaId", "name", "areaName"},
        "list_school_scores": {
            "id",
            "schoolId",
            "schoolName",
            "year",
            "type",
            "score",
            "scoreLine",
            "minScore",
            "registeredResidenceType",
            "accommodationType",
        },
        "list_school_rank_page": {"id", "schoolId", "schoolName", "year", "rank", "minRank"},
        "list_score_layer_page": {"id", "year", "subject", "score", "count"},
        "list_school_ranks": {"id", "schoolId", "schoolName", "year", "rank", "minRank"},
        "list_schools": {
            "id",
            "schoolId",
            "name",
            "schoolName",
            "areaId",
            "areaName",
            "schoolType",
            "boardingType",
        },
    }
    default_whitelist = {"id", "name", "schoolName", "year", "score", "rank"}

    for tool_name, payloads in (tool_data or {}).items():
        preview: list[Any] = []
        whitelist = tool_whitelist.get(tool_name, default_whitelist)
        for payload in payloads[:2]:
            if isinstance(payload, dict):
                preview.append({k: payload.get(k) for k in whitelist if k in payload})
        safe_payload["tools"][tool_name] = {
            "count": len(payloads),
            "preview": preview,
        }
    if computed:
        safe_payload["computed"] = computed
    return safe_payload


async def tool_summary(state: AgentState) -> AgentState:
    """工具结果摘要（不暴露隐私字段）。"""
    tool_data = state.get("tool_data", {})
    computed = state.get("computed", {})
    if not tool_data and not computed:
        return {}
    trace = get_current_trace()
    span = start_span(trace, name="node.tool_summary", input_data={"tool_count": len(tool_data)})
    group_id = state.get("tool_group_id")
    emit_event(state, "tool.summary.start", {"stage": "tools"}, status="running", step_id="tool.summary", group_id=group_id)
    safe_payload = _sanitize_tool_data(tool_data, computed)
    prompt = [
        {"role": "system", "content": tool_summary_system_prompt()},
        {"role": "user", "content": json.dumps(safe_payload, ensure_ascii=False)},
    ]
    enable_think = _extract_enable_think(state)
    show_think = False
    await _stream_llm(
        state,
        prompt,
        "tool.summary.delta",
        step_id="tool.summary",
        enable_think=enable_think,
        show_think=show_think,
    )
    status = "failed" if state.get("tool_errors") else "succeeded"
    emit_event(state, "tool.summary.end", {"stage": "tools"}, status=status, step_id="tool.summary", group_id=group_id)
    emit_event(state, "tool.end", {"group_id": group_id}, status=status, group_id=group_id)
    end_span(span, output={"status": status})
    return {}


async def synth_final(state: AgentState) -> AgentState:
    """最终 summary（含 think/answer），用于落库与返回。"""
    query = state.get("query")
    context_block = build_context_block(state.get("policy_context", []))
    tool_data = state.get("tool_data", {})
    computed = state.get("computed", {})
    trace = get_current_trace()
    span = start_span(trace, name="node.synth_final", input_data={"tool_count": len(tool_data)})
    prompt = [
        {"role": "system", "content": final_synth_system_prompt()},
        {
            "role": "user",
            "content": (
                f"问题：{state['question']}\n"
                f"意图：{query.intent if query else '政策'}\n"
                f"政策上下文：\n{context_block}\n"
                f"工具数据(json)：{json.dumps(tool_data, ensure_ascii=False)[:2000]}\n"
                f"计算结果(json)：{json.dumps(computed, ensure_ascii=False)[:2000]}"
            ),
        },
    ]
    enable_think = _extract_enable_think(state)
    show_think = enable_think
    emit_event(state, "summary.start", {"stage": "final"}, status="running", step_id="summary")
    answer = await _stream_llm(
        state,
        prompt,
        "summary.delta",
        step_id="summary",
        think_event_name="summary.think.delta",
        think_start_event="summary.think.start",
        think_end_event="summary.think.end",
        think_step_id="summary.think",
        emit_content_events=True,
        enable_think=enable_think,
        show_think=show_think,
    )
    final_payload = {
        "answer": answer,
        "citations": [c.model_dump() for c in state.get("citations", [])],
        "meta": {
            "intent": query.intent if query else "政策",
            "tool_rounds": state.get("tool_round", 0),
            "tool_errors": state.get("tool_errors", []),
        },
    }
    emit_event(state, "summary.end", final_payload, status="succeeded", step_id="summary")
    end_span(span, output={"answer_len": len(answer)})
    return {"final": final_payload}
