from __future__ import annotations

import uuid
from typing import Any

from langchain_core.messages import AIMessage

from app.nodes.state import AgentState, MAX_TOOL_ROUNDS
from app.nodes.utils import find_candidates
from src.exam_agent.services.events import emit_event


def plan_tools(state: AgentState) -> AgentState:
    """规则式工具规划器：按意图和槽位拼 tool_calls。"""
    query = state.get("query")
    tool_round = state.get("tool_round", 0)
    tool_data = state.get("tool_data", {})
    resolved_school_id = state.get("resolved_school_id")
    resolved_area_id = state.get("resolved_area_id")
    if not query or not state.get("need_tools"):
        ai_message = AIMessage(content="无需工具调用。", tool_calls=[])
        return {"messages": [ai_message]}
    if tool_round >= MAX_TOOL_ROUNDS:
        ai_message = AIMessage(content="工具调用轮次已达上限。", tool_calls=[])
        return {"messages": [ai_message]}

    tool_calls: list[dict[str, Any]] = []
    updates: dict[str, Any] = {"tool_round": tool_round}

    if query.area_name and not resolved_area_id:
        if not tool_data.get("list_area_page"):
            tool_calls.append(
                {
                    "id": f"call_list_area_page_{tool_round}",
                    "name": "list_area_page",
                    "args": {"name": query.area_name, "page_no": 1, "page_size": 5},
                }
            )
        else:
            candidates = find_candidates(tool_data, "list_area_page")
            if len(candidates) == 1:
                resolved_area_id = candidates[0].get("id") or candidates[0].get("areaId")
                updates["resolved_area_id"] = resolved_area_id

    if query.school_name and not resolved_school_id:
        if not tool_data.get("list_schools"):
            tool_calls.append(
                {
                    "id": f"call_list_schools_{tool_round}",
                    "name": "list_schools",
                    "args": {
                        "name": query.school_name,
                        "area_id": resolved_area_id,
                        "school_type": query.school_type,
                        "boarding_type": query.boarding_type,
                    },
                }
            )
        else:
            candidates = find_candidates(tool_data, "list_schools")
            if len(candidates) == 1:
                resolved_school_id = candidates[0].get("id") or candidates[0].get("schoolId")
                updates["resolved_school_id"] = resolved_school_id
            elif len(candidates) > 1:
                updates["resolved_school_id"] = None
                ai_message = AIMessage(content="需要学校消歧。", tool_calls=[])
                return {**updates, "messages": [ai_message]}

    if not tool_calls:
        if query.intent == "分数":
            tool_calls.append(
                {
                    "id": f"call_list_school_scores_{tool_round}",
                    "name": "list_school_scores",
                    "args": {
                        "year": query.year,
                        "score_type": query.score_type or 1,
                        "school_id": resolved_school_id,
                        "registered_residence_type": query.registered_residence_type,
                        "accommodation_type": query.accommodation_type,
                    },
                }
            )
        elif query.intent == "排名":
            tool_calls.append(
                {
                    "id": f"call_list_school_ranks_{tool_round}",
                    "name": "list_school_ranks",
                    "args": {"school_id": resolved_school_id, "year": query.year},
                }
            )
        elif query.intent in {"推荐", "混合"}:
            tool_calls.append(
                {
                    "id": f"call_list_school_scores_{tool_round}",
                    "name": "list_school_scores",
                    "args": {
                        "year": query.year,
                        "score_type": query.score_type or 1,
                        "school_id": resolved_school_id,
                        "registered_residence_type": query.registered_residence_type,
                        "accommodation_type": query.accommodation_type,
                    },
                }
            )
            tool_calls.append(
                {
                    "id": f"call_list_school_ranks_{tool_round}",
                    "name": "list_school_ranks",
                    "args": {"school_id": resolved_school_id, "year": query.year},
                }
            )
        elif query.intent == "学校信息":
            tool_calls.append(
                {
                    "id": f"call_list_schools_{tool_round}",
                    "name": "list_schools",
                    "args": {
                        "name": query.school_name,
                        "area_id": resolved_area_id,
                        "school_type": query.school_type,
                        "boarding_type": query.boarding_type,
                    },
                }
            )

    updates["tool_round"] = tool_round + 1
    tool_group_id = state.get("tool_group_id") or uuid.uuid4().hex
    updates["tool_group_id"] = tool_group_id
    if tool_calls and not state.get("tool_started"):
        emit_event(
            state,
            "tool.start",
            {"group_id": tool_group_id},
            status="running",
            group_id=tool_group_id,
        )
        updates["tool_started"] = True
    for call in tool_calls:
        emit_event(
            state,
            "tool.call",
            {
                "toolCallId": call["id"],
                "apiName": call["name"],
                "arguments": call["args"],
            },
            status="queued",
            step_id=call["id"],
            group_id=tool_group_id,
        )
    ai_message = AIMessage(content="已准备工具调用。", tool_calls=tool_calls)
    return {**updates, "messages": [ai_message]}
