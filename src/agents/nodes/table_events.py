from __future__ import annotations

from typing import Any

from src.agents.nodes.state import AgentState
from src.agents.nodes.utils import extract_records
from src.app.tables.tool_table_schemas import TOOL_TABLE_SCHEMAS, build_table_payload
from src.agents.services.events import emit_event

TOOL_NAME_ALIASES: dict[str, str] = {
    "list_school_page": "list_school",
    "list_area_page": "list_area",
    "list_school_rank_page": "list_school_rank",
    "list_score_layer_page": "list_score_layer",
}


def _payload_is_success(payload: object) -> bool:
    return not (isinstance(payload, dict) and payload.get("error"))


def _collect_tool_rows(tool_data: dict[str, list[Any]], tool_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in tool_data.get(tool_name, []):
        if not _payload_is_success(payload):
            continue
        rows.extend(extract_records(payload))
    return rows


def emit_table_events(state: AgentState) -> None:
    tool_data = state.get("tool_data", {})
    for tool_name in TOOL_TABLE_SCHEMAS.keys():
        source_tool_name = TOOL_NAME_ALIASES.get(tool_name, tool_name)
        rows = _collect_tool_rows(tool_data, source_tool_name)
        if len(rows) < 2:
            continue
        payload = build_table_payload(tool_name, rows)
        if not payload:
            continue
        event_tool_name = source_tool_name
        payload["toolName"] = event_tool_name
        emit_event(
            state,
            f"table.{event_tool_name}",
            payload,
            status="succeeded",
            step_id=f"table.{event_tool_name}",
        )
