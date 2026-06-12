from __future__ import annotations

from copy import deepcopy
from typing import Any


# 工具参数 -> 后端参数名映射。
TOOL_PARAM_MAPPINGS: dict[str, dict[str, str]] = {
    "list_school": {
        "name": "name",
        "area_id": "areaId",
        "school_type": "schoolType",
        "boarding_type": "boardingType",
    },
    "list_area": {
        "name": "name",
    },
    "list_school_scores": {
        "year": "year",
        "score_type": "type",
        "school_id": "schoolId",
        "school_name": "school_name",
        "registered_residence_type": "registeredResidenceType",
        "accommodation_type": "accommodationType",
    },
    "list_school_rank": {
        "school_id": "schoolId",
        "year": "year",
    },
    "list_score_layer": {
        "year": "year",
        "subject": "subject",
    },
    "list_school_ranks": {
        "school_id": "schoolId",
        "year": "year",
    },
    "list_schools": {
        "name": "name",
        "area_id": "areaId",
        "school_type": "schoolType",
        "boarding_type": "boardingType",
    },
}


# 学校工具参照数据：
# - method: HTTP 方法
# - path: 接口路径
# - description: 供 LLM 决策的工具描述
# - params: 参数类型/枚举/说明
SCHOOL_TOOL_SPECS: dict[str, dict[str, Any]] = {
    "list_school": {
        "method": "POST",
        "path": "/sys/school/list",
        "description": "查询学校列表（不分页模式）。适用于按学校名、区域、学校类型、住宿类型筛选学校。",
        "when_to_use": "需要学校候选集做消歧、筛选、推荐前置检索时。",
        "required": [],
        "params": {
            "name": {"type": "string", "description": "学校名称，支持模糊匹配。"},
            "area_id": {"type": "string", "description": "区域ID。"},
            "school_type": {
                "type": "integer",
                "enum": [0, 1, 2, 3],
                "description": "学校类型：0公办普高，1民办普高，2中职，3综合。",
            },
            "boarding_type": {
                "type": "integer",
                "enum": [0, 1, 2],
                "description": "住宿类型：0住宿，1走读，2其他。",
            },
        },
    },
    "list_area": {
        "method": "POST",
        "path": "/sys/area/list",
        "description": "查询区域列表（不分页模式）。适用于根据区域名反查 area_id。",
        "when_to_use": "用户提供区域名称但未提供区域ID时。",
        "required": [],
        "params": {
            "name": {"type": "string", "description": "区域名称，支持模糊匹配。"},
        },
    },
    "list_school_scores": {
        "method": "GET",
        "path": "/sys/score/listByCondition",
        "description": "查询学校分数线列表。适用于分数咨询、分数对比、推荐前置打分。",
        "when_to_use": "问题涉及学校录取分数、分数线变化或按分数筛学校时。",
        "required": [],
        "params": {
            "year": {"type": "integer", "description": "年份；后端要求必传，默认当前年。"},
            "score_type": {
                "type": "integer",
                "enum": [0, 1, 2],
                "description": "分数类型：0指标，1一批次，2其他。",
            },
            "school_id": {"type": "string", "description": "学校ID。"},
            "school_name": {"type": "string", "description": "学校名称（school_id 缺失时可传）。"},
            "registered_residence_type": {
                "type": "integer",
                "enum": [0, 1, 2],
                "description": "户籍类型：0AC类，1D类，2综合。",
            },
            "accommodation_type": {
                "type": "integer",
                "enum": [0, 1],
                "description": "住宿类型：0住宿，1走读。",
            },
        },
    },
    "list_school_rank": {
        "method": "POST",
        "path": "/sys/rank/list",
        "description": "查询学校排名列表（不分页模式）。",
        "when_to_use": "问题涉及学校排名、位次或排名对比时。",
        "required": [],
        "params": {
            "school_id": {"type": "string", "description": "学校ID。"},
            "year": {"type": "integer", "description": "年份。"},
        },
    },
    "list_score_layer": {
        "method": "POST",
        "path": "/sys/scoreLayer/list",
        "description": "查询分数分层数据（不分页模式）。",
        "when_to_use": "问题涉及某年某科目分层线、分层人数分布时。",
        "required": [],
        "params": {
            "year": {"type": "integer", "description": "年份，默认当前年。"},
            "subject": {
                "type": "integer",
                "enum": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                "description": "科目：0语文，1数学，2英语，3物理，4化学，5生物，6历史，7地理，8政治，9综合。",
            },
        },
    },
    "list_school_ranks": {
        "method": "GET",
        "path": "/sys/rank/listAll",
        "description": "查询学校排名列表（listAll）。",
        "when_to_use": "需要稳定拉取某学校/某年份排名数据时。",
        "required": [],
        "params": {
            "school_id": {"type": "string", "description": "学校ID。"},
            "year": {"type": "integer", "description": "年份。"},
        },
    },
    "list_schools": {
        "method": "GET",
        "path": "/sys/school/listAll",
        "description": "查询学校列表（listAll）。",
        "when_to_use": "需要通过 GET 拉取全量学校列表时。",
        "required": [],
        "params": {
            "name": {"type": "string", "description": "学校名称，支持模糊匹配。"},
            "area_id": {"type": "string", "description": "区域ID。"},
            "school_type": {
                "type": "integer",
                "enum": [0, 1, 2, 3],
                "description": "学校类型：0公办普高，1民办普高，2中职，3综合。",
            },
            "boarding_type": {
                "type": "integer",
                "enum": [0, 1, 2],
                "description": "住宿类型：0住宿，1走读，2其他。",
            },
        },
    },
}


def build_school_tool_schemas() -> list[dict[str, Any]]:
    """将参照数据转为 LLM 的 function tool schema。"""
    schemas: list[dict[str, Any]] = []
    for tool_name, spec in SCHOOL_TOOL_SPECS.items():
        properties: dict[str, Any] = {}
        for param_name, param_spec in (spec.get("params") or {}).items():
            item = deepcopy(param_spec)
            item_type = item.pop("type", "string")
            item["anyOf"] = [{"type": item_type}, {"type": "null"}]
            properties[param_name] = item
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": spec.get("description") or "",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": list(spec.get("required") or []),
                        "additionalProperties": False,
                    },
                },
            }
        )
    return schemas
