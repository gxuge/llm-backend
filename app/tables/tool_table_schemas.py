from __future__ import annotations

from typing import Any


ToolSchema = dict[str, Any]


# tool -> 表格结构映射（统一由 Python 产出）
TOOL_TABLE_SCHEMAS: dict[str, ToolSchema] = {
    "list_schools": {
        "tableId": "school_list",
        "title": "学校列表",
        "schema": [
            {"key": "schoolName", "label": "学校名称", "type": "string"},
            {"key": "areaName", "label": "地区", "type": "string"},
            {"key": "schoolType", "label": "学校类型", "type": "number"},
            {"key": "boardingType", "label": "住宿类型", "type": "number"},
        ],
    },
    "list_school_page": {
        "tableId": "school_page",
        "title": "学校分页",
        "schema": [
            {"key": "schoolName", "label": "学校名称", "type": "string"},
            {"key": "areaName", "label": "地区", "type": "string"},
            {"key": "schoolType", "label": "学校类型", "type": "number"},
            {"key": "boardingType", "label": "住宿类型", "type": "number"},
        ],
    },
    "list_school_scores": {
        "tableId": "school_scores",
        "title": "学校分数",
        "schema": [
            {"key": "schoolName", "label": "学校名称", "type": "string"},
            {"key": "year", "label": "年份", "type": "number"},
            {"key": "type", "label": "类型", "type": "number"},
            {"key": "score", "label": "分数", "type": "number"},
            {"key": "scoreLine", "label": "分数线", "type": "number"},
            {"key": "registeredResidenceType", "label": "户籍类型", "type": "number"},
            {"key": "accommodationType", "label": "住宿类型", "type": "number"},
        ],
    },
    "list_school_rank_page": {
        "tableId": "school_rank_page",
        "title": "学校排名(分页)",
        "schema": [
            {"key": "schoolName", "label": "学校名称", "type": "string"},
            {"key": "year", "label": "年份", "type": "number"},
            {"key": "rank", "label": "排名", "type": "number"},
            {"key": "minRank", "label": "最低名次", "type": "number"},
        ],
    },
    "list_school_ranks": {
        "tableId": "school_ranks",
        "title": "学校排名",
        "schema": [
            {"key": "schoolName", "label": "学校名称", "type": "string"},
            {"key": "year", "label": "年份", "type": "number"},
            {"key": "rank", "label": "排名", "type": "number"},
            {"key": "minRank", "label": "最低名次", "type": "number"},
        ],
    },
    "list_score_layer_page": {
        "tableId": "score_layers",
        "title": "分数段统计",
        "schema": [
            {"key": "year", "label": "年份", "type": "number"},
            {"key": "subject", "label": "科目", "type": "number"},
            {"key": "score", "label": "分数", "type": "number"},
            {"key": "count", "label": "人数", "type": "number"},
        ],
    },
}


def build_table_payload(tool_name: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """根据工具名称与数据行生成表格 payload。"""
    schema = TOOL_TABLE_SCHEMAS.get(tool_name)
    if not schema:
        return None
    columns = schema.get("schema") or []
    row_keys = [column["key"] for column in columns if "key" in column]
    mapped_rows = [{key: row.get(key) for key in row_keys} for row in rows if isinstance(row, dict)]
    return {
        "toolName": tool_name,
        "tableId": schema.get("tableId") or tool_name,
        "title": schema.get("title") or tool_name,
        "schema": columns,
        "rows": mapped_rows,
        "meta": schema.get("meta") or {},
    }
