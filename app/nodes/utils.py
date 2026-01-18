from __future__ import annotations

import datetime
import re
from typing import Any

from app.schemas.exam_agent import QuerySpec, TableColumn, TableSpec
from app.nodes.state import INTENT_OPTIONS


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
    if any(k in text for k in ["分数", "分数线", "录取", "投档", "上线"]):
        intent = "分数"
    elif any(k in text for k in ["排名", "位次", "位次线"]):
        intent = "排名"
    elif any(k in text for k in ["推荐", "冲稳保", "建议"]):
        intent = "推荐"
    elif any(k in text for k in ["学校", "中学", "高中", "职校"]):
        intent = "学校信息"
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
        return "未命中政策上下文。"
    return "\n\n".join(policy_context[:6])
