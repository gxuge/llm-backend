from __future__ import annotations

from app.nodes.state import AgentState
from app.nodes.utils import build_table_from_rows, find_candidates
from app.schemas.exam_agent import TableSpec
from src.exam_agent.services.events import emit_event


def viz_builder(state: AgentState) -> AgentState:
    """将工具结果拼装为 Table/Chart，并输出 viz.* 事件。"""
    query = state.get("query")
    tool_data = state.get("tool_data", {})
    computed = state.get("computed", {})

    table = TableSpec(table_id="empty", title="No data", row_key="id", columns=[], rows=[])

    if tool_data.get("list_schools") and not state.get("resolved_school_id"):
        rows = find_candidates(tool_data, "list_schools")
        table = build_table_from_rows(rows, "学校候选", "school_candidates")
    elif tool_data.get("list_school_scores"):
        rows = find_candidates(tool_data, "list_school_scores")
        table = build_table_from_rows(rows, "分数线列表", "school_scores")
    elif tool_data.get("list_school_ranks"):
        rows = find_candidates(tool_data, "list_school_ranks")
        table = build_table_from_rows(rows, "排名列表", "school_ranks")
    elif query and query.intent == "政策":
        table = build_table_from_rows([], "政策上下文", "policy_context")

    if computed.get("recommendations"):
        rows = computed["recommendations"]
        table = build_table_from_rows(rows, "推荐结果", "recommendations")

    # 表格事件已移至 summary 结束后统一输出
    return {"table": table, "chart": None}
