from __future__ import annotations

from collections.abc import Callable
from typing import Any, Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from src.exam_agent.schemas.types import ChartSpec, Citation, QuerySpec, TableSpec

StreamWriter = Callable[[Any], None]


class AgentState(TypedDict, total=False):
    run_id: str
    sequence_number: int
    question: str
    query: QuerySpec
    policy_context: list[str]
    citations: list[Citation]
    need_tools: bool
    tool_round: int
    tool_group_id: str | None
    tool_data: dict[str, list[Any]]
    tool_errors: list[str]
    resolved_school_id: str | None
    resolved_area_id: str | None
    table: TableSpec
    chart: ChartSpec | None
    computed: dict[str, Any]
    need_compute_rule: bool
    need_compute_llm: bool
    need_compute: bool
    final: dict[str, Any]
    writer: StreamWriter | None
    messages: Annotated[list[AnyMessage], add_messages]
