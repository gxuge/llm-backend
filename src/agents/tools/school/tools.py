from __future__ import annotations

import datetime
from typing import Any

from langchain_core.tools import tool

from src.agents.tools.school.client import clean_params, request_school_api
from src.agents.tools.school.specs import SCHOOL_TOOL_SPECS, TOOL_PARAM_MAPPINGS


def _map_to_api_params(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    # 按参照映射把工具参数名转换为后端接口参数名。
    mapping = TOOL_PARAM_MAPPINGS[tool_name]
    mapped: dict[str, Any] = {}
    for src_key, dst_key in mapping.items():
        mapped[dst_key] = params.get(src_key)
    return clean_params(mapped)


async def _call_school_tool(tool_name: str, params: dict[str, Any]) -> Any:
    # 统一使用 specs 中的 method/path 调用后端。
    spec = SCHOOL_TOOL_SPECS[tool_name]
    api_params = _map_to_api_params(tool_name, params)
    return await request_school_api(spec["path"], method=spec["method"], params=api_params)


@tool("list_school", description=SCHOOL_TOOL_SPECS["list_school"]["description"])
async def list_school(
    name: str | None = None,
    area_id: str | None = None,
    school_type: int | None = None,
    boarding_type: int | None = None,
) -> Any:
    """查询学校列表。"""
    return await _call_school_tool(
        "list_school",
        {
            "name": name,
            "area_id": area_id,
            "school_type": school_type,
            "boarding_type": boarding_type,
        },
    )


@tool("list_area", description=SCHOOL_TOOL_SPECS["list_area"]["description"])
async def list_area(
    name: str | None = None,
) -> Any:
    """查询区域列表。"""
    return await _call_school_tool(
        "list_area",
        {"name": name},
    )


@tool("list_school_scores", description=SCHOOL_TOOL_SPECS["list_school_scores"]["description"])
async def list_school_scores(
    year: int | None = None,
    score_type: int | None = None,
    school_id: str | None = None,
    school_name: str | None = None,
    registered_residence_type: int | None = None,
    accommodation_type: int | None = None,
) -> Any:
    """查询学校分数线。"""
    if year is None:
        year = datetime.date.today().year
    return await _call_school_tool(
        "list_school_scores",
        {
            "year": year,
            "score_type": score_type,
            "school_id": school_id,
            "school_name": school_name,
            "registered_residence_type": registered_residence_type,
            "accommodation_type": accommodation_type,
        },
    )


@tool(
    "list_school_rank",
    description=SCHOOL_TOOL_SPECS["list_school_rank"]["description"],
)
async def list_school_rank(
    school_id: str | None = None,
    year: int | None = None,
) -> Any:
    """查询学校排名。"""
    return await _call_school_tool(
        "list_school_rank",
        {
            "school_id": school_id,
            "year": year,
        },
    )


@tool(
    "list_score_layer",
    description=SCHOOL_TOOL_SPECS["list_score_layer"]["description"],
)
async def list_score_layer(
    year: int | None = None,
    subject: int | None = None,
) -> Any:
    """查询分数分层。"""
    if year is None:
        year = datetime.date.today().year
    return await _call_school_tool(
        "list_score_layer",
        {"year": year, "subject": subject},
    )


@tool("list_school_ranks", description=SCHOOL_TOOL_SPECS["list_school_ranks"]["description"])
async def list_school_ranks(
    school_id: str | None = None,
    year: int | None = None,
) -> Any:
    """查询学校排名（不分页）。"""
    return await _call_school_tool("list_school_ranks", {"school_id": school_id, "year": year})


@tool("list_schools", description=SCHOOL_TOOL_SPECS["list_schools"]["description"])
async def list_schools(
    name: str | None = None,
    area_id: str | None = None,
    school_type: int | None = None,
    boarding_type: int | None = None,
) -> Any:
    """查询学校列表（不分页）。"""
    return await _call_school_tool(
        "list_schools",
        {
            "name": name,
            "area_id": area_id,
            "school_type": school_type,
            "boarding_type": boarding_type,
        },
    )
