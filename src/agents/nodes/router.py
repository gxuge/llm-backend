from __future__ import annotations

from src.app.core.langfuse import end_span, get_current_trace, start_span
from src.agents.nodes.state import AgentState
from src.agents.services.events import emit_event


def route_tools(state: AgentState) -> AgentState:
    query = state.get("query")
    intent = query.intent if query else "政策"
    trace = get_current_trace()
    span = start_span(trace, name="node.route_tools", input_data={"intent": intent})
    need_tools = intent in {"分数", "排名", "推荐", "学校信息", "混合"}
    if need_tools and query and query.registered_residence_type is None:
        query.registered_residence_type = 2
    need_compute_rule = False
    if query and query.score is not None and query.intent in {"推荐", "混合"}:
        need_compute_rule = True
    emit_event(
        state,
        "trace.event",
        {"intent": intent, "need_tools": need_tools},
        status="running",
    )
    end_span(span, output={"need_tools": need_tools, "need_compute_rule": need_compute_rule})
    return {"need_tools": need_tools, "query": query, "need_compute_rule": need_compute_rule}
