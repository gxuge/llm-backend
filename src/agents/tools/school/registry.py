from __future__ import annotations

from src.agents.tools.school.specs import (
    SCHOOL_TOOL_SPECS,
    TOOL_PARAM_MAPPINGS,
    build_school_tool_schemas,
)
from src.agents.tools.school.tools import (
    list_area,
    list_school,
    list_school_rank,
    list_school_ranks,
    list_school_scores,
    list_schools,
    list_score_layer,
)


# 学校工具注册表：供 planner/tool_node 执行使用。
SCHOOL_TOOLS = [
    list_school,
    list_area,
    list_school_scores,
    list_school_rank,
    list_score_layer,
    list_school_ranks,
    list_schools,
]

# 学校工具的 LLM schema：供 router 的 tool_call 判定使用。
SCHOOL_TOOL_SCHEMAS = build_school_tool_schemas()

__all__ = [
    "SCHOOL_TOOLS",
    "SCHOOL_TOOL_SCHEMAS",
    "SCHOOL_TOOL_SPECS",
    "TOOL_PARAM_MAPPINGS",
    "list_school",
    "list_area",
    "list_school_scores",
    "list_school_rank",
    "list_score_layer",
    "list_school_ranks",
    "list_schools",
]
