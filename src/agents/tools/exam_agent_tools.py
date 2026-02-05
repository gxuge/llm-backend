from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from src.app.schemas.exam_agent import QuerySpec


def _find_candidates(tool_data: dict[str, list[Any]], tool_name: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for payload in tool_data.get(tool_name, []):
        if isinstance(payload, dict):
            for key in ("records", "result", "data", "rows"):
                if isinstance(payload.get(key), list):
                    items.extend(payload.get(key) or [])
                    break
            else:
                items.append(payload)
        elif isinstance(payload, list):
            items.extend([item for item in payload if isinstance(item, dict)])
    return items


def _compute_recommendations(query: QuerySpec | None, tool_data: dict[str, list[Any]]) -> dict[str, Any]:
    computed: dict[str, Any] = {}
    if query and query.intent in {"推荐", "混合"} and query.score:
        scores = _find_candidates(tool_data, "list_school_scores")
        diffs = []
        for item in scores:
            raw_score = (
                item.get("score")
                or item.get("scoreLine")
                or item.get("minScore")
                or item.get("line")
            )
            if isinstance(raw_score, (int, float)):
                diff = int(query.score - raw_score)
                tag = "safe" if diff >= 10 else "steady" if diff >= -5 else "reach"
                diffs.append({**item, "score_diff": diff, "bucket": tag})
        if diffs:
            computed["recommendations"] = sorted(diffs, key=lambda x: x["score_diff"], reverse=True)
    return computed


@tool("compute_recommendations")
async def compute_recommendations(query: dict | None = None, tool_data: dict | None = None) -> dict[str, Any]:
    """基于分数线与用户分数计算冲稳保推荐结果。"""
    parsed_query = QuerySpec(**query) if isinstance(query, dict) else None
    payload = tool_data if isinstance(tool_data, dict) else {}
    return _compute_recommendations(parsed_query, payload)
