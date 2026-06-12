from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from src.agents.nodes.utils import extract_records


TOOL_NAME_ALIASES: dict[str, str] = {
    "list_school_page": "list_school",
    "list_area_page": "list_area",
    "list_school_rank_page": "list_school_rank",
    "list_score_layer_page": "list_score_layer",
}


TOOL_FIELD_WHITELIST: dict[str, list[str]] = {
    "list_school": ["id", "schoolId", "name", "schoolName", "areaId", "areaName", "schoolType", "boardingType"],
    "list_area": ["id", "areaId", "name", "areaName"],
    "list_school_scores": [
        "id",
        "schoolId",
        "schoolName",
        "year",
        "type",
        "score",
        "scoreLine",
        "minScore",
        "registeredResidenceType",
        "accommodationType",
    ],
    "list_school_rank": ["id", "schoolId", "schoolName", "year", "rank", "minRank"],
    "list_score_layer": ["id", "year", "subject", "score", "count"],
    "list_school_ranks": ["id", "schoolId", "schoolName", "year", "rank", "minRank"],
    "list_schools": ["id", "schoolId", "name", "schoolName", "areaId", "areaName", "schoolType", "boardingType"],
}


FIELD_LABELS_ZH: dict[str, str] = {
    "id": "ID",
    "schoolId": "学校ID",
    "name": "名称",
    "schoolName": "学校名称",
    "areaId": "区域ID",
    "areaName": "区域名称",
    "schoolType": "学校类型",
    "boardingType": "住宿类型",
    "year": "年份",
    "type": "分数类型",
    "score": "分数",
    "scoreLine": "分数线",
    "minScore": "最低分",
    "registeredResidenceType": "户籍类型",
    "accommodationType": "住宿类型",
    "rank": "排名",
    "minRank": "最低排名",
    "subject": "科目",
    "count": "人数",
}


def _normalize_tool_name(tool_name: str) -> str:
    return TOOL_NAME_ALIASES.get(tool_name, tool_name)


def _parse_failed_tool_names(tool_errors: list[str]) -> set[str]:
    failed: set[str] = set()
    for item in tool_errors:
        if not isinstance(item, str) or not item.strip():
            continue
        name = item.split(":", 1)[0].strip()
        if name:
            failed.add(_normalize_tool_name(name))
    return failed


def _is_error_payload(payload: Any) -> bool:
    return isinstance(payload, dict) and bool(payload.get("error"))


def _flatten_rows(payloads: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in payloads:
        if _is_error_payload(payload):
            continue
        rows.extend(extract_records(payload))
    return [item for item in rows if isinstance(item, dict)]


def _choose_columns(tool_name: str, rows: list[dict[str, Any]]) -> list[str]:
    whitelist = TOOL_FIELD_WHITELIST.get(tool_name)
    if whitelist:
        return whitelist
    if not rows:
        return []
    return list(rows[0].keys())


def _format_cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not columns:
        return ""
    headers = [FIELD_LABELS_ZH.get(col, col) for col in columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        values = [_format_cell(row.get(col)) for col in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def build_tool_summary_payload(
    tool_data: dict[str, list[Any]],
    computed: dict[str, Any],
    tool_errors: list[str],
) -> dict[str, Any]:
    failed_tools = _parse_failed_tool_names(tool_errors)
    payload: dict[str, Any] = {
        "tools": {},
        "tool_errors": tool_errors,
    }

    for raw_tool_name, payloads in (tool_data or {}).items():
        normalized_name = _normalize_tool_name(raw_tool_name)
        if normalized_name in failed_tools:
            continue
        rows = _flatten_rows(payloads)
        columns = _choose_columns(normalized_name, rows)
        mapped_rows = [{col: row.get(col) for col in columns} for row in rows]
        payload["tools"][normalized_name] = {
            "count": len(rows),
            "rows": mapped_rows,
            "markdown_table": _markdown_table(mapped_rows, columns),
        }

    if computed:
        payload["computed"] = computed
    return payload


def build_tool_summary_prompt_payload(summary_payload: dict[str, Any]) -> dict[str, Any]:
    prompt_payload = deepcopy(summary_payload)
    prompt_payload.pop("tool_errors", None)
    tools = prompt_payload.get("tools") or {}
    if isinstance(tools, dict):
        for _, item in tools.items():
            if isinstance(item, dict):
                item.pop("markdown_table", None)
    return prompt_payload
