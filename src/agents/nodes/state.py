from __future__ import annotations

from collections.abc import Callable
from typing import Any, Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from src.app.schemas.exam_agent import ChartSpec, Citation, QuerySpec, TableSpec

StreamWriter = Callable[[Any], None]


class AgentState(TypedDict, total=False):
    run_id: str
    sequence_number: int
    question: str
    query: QuerySpec
    policy_context: list[str]
    citations: list[Citation]
    need_tools: bool
    # 规则门控结果：是否需要进入工具分支。
    need_tools_rule: bool
    # LLM 门控结果：True/False；未调用或失败时为 None。
    need_tools_llm: bool | None
    # 原生 tool_call 门控结果：True/False；未调用或失败时为 None。
    need_tools_tool_call: bool | None
    suggested_tool_calls: list[dict[str, Any]]
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
    access_token: str | None
    enable_think: bool
    show_think: bool
    writer: StreamWriter | None
    messages: Annotated[list[AnyMessage], add_messages]


INTENT_OPTIONS = ["政策", "分数", "排名", "推荐", "学校信息", "混合"]
MAX_TOOL_ROUNDS = 3
