from __future__ import annotations

import datetime
import re
from typing import Any

from src.app.schemas.exam_agent import QuerySpec, TableColumn, TableSpec
from src.agents.nodes.state import INTENT_OPTIONS


def coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def normalize_query(raw: dict[str, Any]) -> QuerySpec:
    year = coerce_int(raw.get("year"))
    if year is None:
        year = datetime.date.today().year
    intent = raw.get("intent") or "政策"
    if intent not in INTENT_OPTIONS:
        intent = "政策"
    return QuerySpec(
        year=year,
        school_name=raw.get("school_name") or raw.get("schoolName"),
        area_name=raw.get("area_name") or raw.get("areaName"),
        score=coerce_int(raw.get("score")),
        intent=intent,
        school_type=coerce_int(raw.get("school_type")),
        boarding_type=coerce_int(raw.get("boarding_type")),
        score_type=coerce_int(raw.get("score_type")),
        registered_residence_type=coerce_int(raw.get("registered_residence_type")),
        accommodation_type=coerce_int(raw.get("accommodation_type")),
    )


def fallback_extract(question: str) -> QuerySpec:
    text = question.lower()
    year = datetime.date.today().year
    match = re.search(r"(20\d{2})", question)
    if match:
        year = int(match.group(1))
    intent = "政策"
    if any(k in text for k in ["\u5206\u6570", "\u5f55\u53d6", "\u6295\u6863", "\u4e0a\u7ebf"]):
        intent = "分数"
    elif any(k in text for k in ["\u6392\u540d", "\u4f4d\u6b21"]):
        intent = "\u6392\u540d"
    elif any(k in text for k in ["\u63a8\u8350", "\u51b2\u7a33", "\u5efa\u8bae"]):
        intent = "\u63a8\u8350"
    elif any(k in text for k in ["\u5b66\u6821", "\u4e2d\u5b66", "\u9ad8\u4e2d", "\u804c\u6821"]):
        intent = "\u5b66\u6821\u4fe1\u606f"
    school_name = None
    match = re.search(r"([\u4e00-\u9fa5]{2,8}中学)", question)
    if match:
        school_name = match.group(1)
    return QuerySpec(year=year, intent=intent, school_name=school_name)


def split_dataset_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for key in ("records", "result", "data", "rows"):
            if isinstance(payload.get(key), list):
                return list(payload.get(key) or [])
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def merge_tool_data(
    tool_data: dict[str, list[Any]],
    tool_name: str,
    payload: Any,
) -> dict[str, list[Any]]:
    merged = dict(tool_data)
    merged.setdefault(tool_name, []).append(payload)
    return merged


def find_candidates(tool_data: dict[str, list[Any]], tool_name: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for payload in tool_data.get(tool_name, []):
        items.extend(extract_records(payload))
    return items


def build_table_from_rows(rows: list[dict[str, Any]], title: str, table_id: str) -> TableSpec:
    columns: list[TableColumn] = []
    if rows:
        for key in list(rows[0].keys())[:8]:
            columns.append(TableColumn(field=key, title=str(key)))
    row_key = "id" if rows and "id" in rows[0] else (next(iter(rows[0].keys()), "id") if rows else "id")
    return TableSpec(table_id=table_id, title=title, row_key=row_key, columns=columns, rows=rows)


def build_context_block(policy_context: list[str]) -> str:
    if not policy_context:
        return "\u672a\u547d\u4e2d\u653f\u7b56\u4e0a\u4e0b\u6587"
    return "\n\n".join(policy_context[:6])
