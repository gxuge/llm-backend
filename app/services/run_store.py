from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunRecord:
    """单次运行的内存态记录。"""

    status: str
    started_at: int
    trace_id: str
    finished_at: int | None = None
    result: dict[str, Any] = field(default_factory=dict)
    module_summary: dict[str, Any] = field(default_factory=dict)
    subscribers: list[asyncio.Queue[str]] = field(default_factory=list)
    seq_counter: int = 0
    error: dict[str, Any] | None = None
    rag_summary_text: str = ""
    summary_text: str = ""
    think_text: str = ""
    tool_calls: dict[str, dict[str, Any]] = field(default_factory=dict)
    rag_started: bool = False
    rag_ended: bool = False
    think_started: bool = False
    think_ended: bool = False
    summary_started: bool = False
    summary_ended: bool = False
    tools_started: bool = False
    tools_ended: bool = False


class RunStore:
    """最小内存版 RunStore，后续可替换为 Redis/DB。"""

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}
        self._idempotency: dict[str, str] = {}
        self._lock = asyncio.Lock()

    # 创建 run（支持 userId+clientId 幂等）
    async def create_run(self, user_id: str, client_id: str | None) -> tuple[str, RunRecord]:
        async with self._lock:
            if client_id:
                key = f"{user_id}:{client_id}"
                run_id = self._idempotency.get(key)
                if run_id and run_id in self._runs:
                    return run_id, self._runs[run_id]
            run_id = uuid.uuid4().hex
            trace_id = uuid.uuid4().hex
            started_at = int(time.time() * 1000)
            record = RunRecord(
                status="RUNNING",
                started_at=started_at,
                trace_id=trace_id,
                module_summary=_init_module_summary(),
            )
            self._runs[run_id] = record
            if client_id:
                self._idempotency[f"{user_id}:{client_id}"] = run_id
            return run_id, record

    # 查询 run
    async def get_run(self, run_id: str) -> RunRecord | None:
        async with self._lock:
            return self._runs.get(run_id)

    # 订阅事件队列（SSE）
    async def subscribe(self, run_id: str) -> asyncio.Queue[str] | None:
        async with self._lock:
            record = self._runs.get(run_id)
            if not record:
                return None
            queue: asyncio.Queue[str] = asyncio.Queue()
            record.subscribers.append(queue)
            return queue

    # 取消订阅
    async def unsubscribe(self, run_id: str, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            record = self._runs.get(run_id)
            if not record:
                return
            if queue in record.subscribers:
                record.subscribers.remove(queue)

    # 发布事件并更新模块汇总
    async def publish(self, run_id: str, event_name: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            record = self._runs.get(run_id)
            if not record:
                return
            record.seq_counter += 1
            data = {
                "protocolVersion": "1.0",
                "runId": run_id,
                "ts": int(time.time() * 1000),
                "event": event_name,
                "seq": record.seq_counter,
                "payload": payload,
            }
            self._update_summary(record, event_name, payload)
            message = _sse_event(event_name, data)
            for queue in list(record.subscribers):
                queue.put_nowait(message)

    # 基于事件实时更新模块汇总与最终结果
    def _update_summary(self, record: RunRecord, event_name: str, payload: dict[str, Any]) -> None:
        modules = record.module_summary
        if event_name == "run.start":
            record.status = "RUNNING"

        if event_name == "run.error":
            record.status = "FAIL"
            record.error = payload
            modules["summary"]["answerStatus"] = "fail"
            modules["summary"]["error"] = payload
            if record.think_started:
                modules["summary"]["thinkStatus"] = "fail"
            record.finished_at = int(time.time() * 1000)

        if event_name == "rag.start":
            record.rag_started = True
            modules["rag"]["used"] = True
        elif event_name == "rag.summary.start":
            record.rag_started = True
            modules["rag"]["used"] = True
        elif event_name == "rag.hits":
            record.rag_started = True
            modules["rag"]["used"] = True
            count = payload.get("count")
            if count is None:
                hits = payload.get("hits") or []
                count = len(hits)
            modules["rag"]["hitsCount"] += int(count or 0)
        elif event_name == "rag.summary.delta":
            record.rag_summary_text += payload.get("delta", "")
        elif event_name == "rag.error":
            modules["rag"]["status"] = "fail"
            modules["rag"]["error"] = payload
            record.rag_ended = True
        elif event_name == "rag.summary.end":
            modules["rag"]["used"] = True
        elif event_name == "rag.end":
            record.rag_ended = True
            if modules["rag"]["status"] != "fail":
                modules["rag"]["status"] = "success"
            if record.rag_summary_text:
                modules["rag"]["summary"] = record.rag_summary_text

        if event_name == "tool.call":
            modules["tools"]["used"] = True
            record.tools_started = True
            call_id = payload.get("toolCallId") or payload.get("id")
            api_name = payload.get("apiName") or payload.get("tool_name")
            arguments = payload.get("arguments") or payload.get("args")
            if call_id:
                record.tool_calls[call_id] = {
                    "toolCallId": call_id,
                    "apiName": api_name,
                    "status": "running",
                    "arguments": arguments,
                    "resultSummary": None,
                    "error": None,
                }
        elif event_name == "tool.result":
            call_id = payload.get("toolCallId") or payload.get("id")
            if call_id and call_id in record.tool_calls:
                record.tool_calls[call_id]["status"] = "success"
                record.tool_calls[call_id]["resultSummary"] = payload.get("resultSummary")
        elif event_name == "tool.error":
            modules["tools"]["used"] = True
            record.tools_started = True
            call_id = payload.get("toolCallId") or payload.get("id")
            if call_id and call_id in record.tool_calls:
                record.tool_calls[call_id]["status"] = "fail"
                record.tool_calls[call_id]["error"] = payload
        elif event_name == "tool.summary.start":
            modules["tools"]["used"] = True
            record.tools_started = True
        elif event_name == "tool.summary.delta":
            modules["tools"]["used"] = True
            record.tools_started = True
        elif event_name == "tool.summary.end":
            modules["tools"]["used"] = True
            record.tools_started = True
        elif event_name == "tool.end":
            modules["tools"]["used"] = True
            record.tools_ended = True
            calls = list(record.tool_calls.values())
            if calls:
                any_fail = any(call["status"] == "fail" for call in calls)
                any_success = any(call["status"] == "success" for call in calls)
                if any_fail and any_success:
                    modules["tools"]["status"] = "partial"
                elif any_fail:
                    modules["tools"]["status"] = "fail"
                else:
                    modules["tools"]["status"] = "success"
            else:
                modules["tools"]["status"] = "success"
            modules["tools"]["calls"] = calls

        if event_name == "summary.think.start":
            record.think_started = True
        elif event_name == "summary.think.delta":
            record.think_text += payload.get("delta", "")
        elif event_name == "summary.think.end":
            record.think_ended = True
            modules["summary"]["thinkStatus"] = "success"

        if event_name == "summary.start":
            record.summary_started = True
        elif event_name == "summary.delta":
            record.summary_text += payload.get("delta", "")
        elif event_name == "summary.end":
            record.summary_ended = True
            ok = payload.get("ok", True)
            modules["summary"]["answerStatus"] = "success" if ok else "fail"
            record.result["content"] = payload.get("answer") or record.summary_text
            record.result["reasoning"] = payload.get("reasoning") or record.think_text
            record.result["raw"] = payload.get("raw")
            record.finished_at = payload.get("finishedAt") or int(time.time() * 1000)
            if record.status != "FAIL":
                record.status = "SUCCESS" if ok else "FAIL"

        if event_name == "viz.table":
            modules["viz"]["tableStatus"] = "success"
            modules["viz"]["tables"] += 1
        elif event_name == "viz.chart":
            modules["viz"]["chartStatus"] = "success"
            modules["viz"]["charts"] += 1

        if event_name == "run.end":
            ok = payload.get("ok", True)
            if record.status != "FAIL":
                record.status = "SUCCESS" if ok else "FAIL"
            record.finished_at = payload.get("finishedAt") or int(time.time() * 1000)
            if not record.result.get("content"):
                record.result["content"] = record.summary_text
            if not record.result.get("reasoning"):
                record.result["reasoning"] = record.think_text

            if record.rag_started and modules["rag"]["status"] == "not_used":
                modules["rag"]["status"] = "fail" if not record.rag_ended else modules["rag"]["status"]

            if record.tools_started and modules["tools"]["status"] == "not_used":
                calls = list(record.tool_calls.values())
                any_fail = any(call["status"] == "fail" for call in calls)
                any_success = any(call["status"] == "success" for call in calls)
                any_running = any(call["status"] == "running" for call in calls)
                if any_running and any_success:
                    modules["tools"]["status"] = "partial"
                elif any_running or any_fail:
                    modules["tools"]["status"] = "fail"
                else:
                    modules["tools"]["status"] = "success"
                modules["tools"]["calls"] = calls

            if record.think_started and modules["summary"]["thinkStatus"] == "not_used":
                modules["summary"]["thinkStatus"] = "fail"

            if modules["summary"]["answerStatus"] == "not_used":
                modules["summary"]["answerStatus"] = "fail"
            if not ok:
                modules["summary"]["answerStatus"] = "fail"


def _init_module_summary() -> dict[str, Any]:
    """初始化模块汇总状态。"""

    return {
        "rag": {
            "used": False,
            "status": "not_used",
            "hitsCount": 0,
            "error": None,
            "summary": None,
        },
        "tools": {
            "used": False,
            "status": "not_used",
            "calls": [],
        },
        "summary": {
            "thinkStatus": "not_used",
            "answerStatus": "not_used",
            "error": None,
        },
        "viz": {
            "tableStatus": "not_used",
            "chartStatus": "not_used",
            "tables": 0,
            "charts": 0,
        },
    }


def _sse_event(event: str, data_obj: dict[str, Any]) -> str:
    payload = json.dumps(data_obj, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


run_store = RunStore()
