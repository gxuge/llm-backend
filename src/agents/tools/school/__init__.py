from __future__ import annotations

from src.agents.tools.school.client import (
    SchoolApiError,
    SchoolConfigError,
    set_access_token,
)
from src.agents.tools.school.registry import (
    SCHOOL_TOOLS,
    SCHOOL_TOOL_SCHEMAS,
    SCHOOL_TOOL_SPECS,
    TOOL_PARAM_MAPPINGS,
    list_area,
    list_school,
    list_school_rank,
    list_school_ranks,
    list_school_scores,
    list_schools,
    list_score_layer,
)

# 对外导出学校工具域的统一入口。
__all__ = [
    "SchoolConfigError",
    "SchoolApiError",
    "set_access_token",
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
