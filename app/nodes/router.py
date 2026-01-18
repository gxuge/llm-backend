from __future__ import annotations

from app.nodes.state import AgentState
from src.exam_agent.services.events import emit_event


def route_tools(state: AgentState) -> AgentState:
    query = state.get("query")
    intent = query.intent if query else "政策"
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
    return {"need_tools": need_tools, "query": query, "need_compute_rule": need_compute_rule}
