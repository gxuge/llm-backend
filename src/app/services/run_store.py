from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.app.core.config import settings
from src.app.core.redis import get_redis

logger = logging.getLogger(__name__)


class RedisUnavailableError(RuntimeError):
    """Raised when Redis is unavailable or connection is closed."""


@dataclass
class RunRecord:
    """单次运行的状态快照，存储在内存并持久化到 Redis。"""

    status: str
    started_at: int
    trace_id: str
    finished_at: int | None = None
    result: dict[str, Any] = field(default_factory=dict)
    module_summary: dict[str, Any] = field(default_factory=dict)
    subscribers: list = field(default_factory=list)  # 兼容旧字段，占位
    seq_counter: int = 0
    error: dict[str, Any] | None = None
    rag_summary_text: str = ""
    summary_text: str = ""
    think_text: str = ""
    tool_text: str = ""
    tool_calls: dict[str, dict[str, Any]] = field(default_factory=dict)
    rag_started: bool = False
    rag_ended: bool = False
    think_started: bool = False
    think_ended: bool = False
    summary_started: bool = False
    summary_ended: bool = False
    tools_started: bool = False
    tools_ended: bool = False

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "RunRecord":
        # 填充缺省字段，保证字段齐全
        base = RunRecord(
            status=data.get("status", "RUNNING"),
            started_at=data.get("started_at", int(time.time() * 1000)),
            trace_id=data.get("trace_id", uuid.uuid4().hex),
        )
        merged = asdict(base)
        merged.update(data)
        if not merged.get("module_summary"):
            merged["module_summary"] = _init_module_summary()
        return RunRecord(**merged)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RunStore:
    """基于 Redis 的 RunStore，事件默认保存 30 分钟（可配置）。"""

    def __init__(self) -> None:
        self.redis: Redis = get_redis()
        self.ttl_seconds = settings.redis_ttl_minutes * 60
        self._subscriber_tasks: dict[asyncio.Queue[str], asyncio.Task] = {}

    def _raise_redis_error(self, action: str, exc: Exception) -> None:
        logger.error("Redis error during %s: %s", action, exc)
        raise RedisUnavailableError("Redis unavailable") from exc

    def _key_record(self, run_id: str) -> str:
        return f"run:{run_id}:record"

    def _key_idempotency(self, user_id: str, client_id: str) -> str:
        return f"run:idempotency:{user_id}:{client_id}"

    def _channel(self, run_id: str) -> str:
        return f"run:{run_id}:events"

    async def create_run(self, user_id: str, client_id: str | None) -> tuple[str, RunRecord]:
        if client_id:
            idem_key = self._key_idempotency(user_id, client_id)
            try:
                existing = await self.redis.get(idem_key)
            except RedisError as exc:
                self._raise_redis_error("create_run.get_idempotency", exc)
            if existing:
                existing_record = await self.get_run(existing)
                if existing_record:
                    return existing, existing_record

        run_id = uuid.uuid4().hex
        trace_id = uuid.uuid4().hex
        started_at = int(time.time() * 1000)
        record = RunRecord(
            status="RUNNING",
            started_at=started_at,
            trace_id=trace_id,
            module_summary=_init_module_summary(),
        )
        await self._save_run(run_id, record)
        if client_id:
            try:
                await self.redis.set(self._key_idempotency(user_id, client_id), run_id, ex=self.ttl_seconds)
            except RedisError as exc:
                self._raise_redis_error("create_run.set_idempotency", exc)
        return run_id, record

    async def get_run(self, run_id: str) -> RunRecord | None:
        try:
            raw = await self.redis.get(self._key_record(run_id))
        except RedisError as exc:
            self._raise_redis_error("get_run", exc)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return RunRecord.from_dict(data)
        except Exception:
            return None

    async def subscribe(self, run_id: str) -> asyncio.Queue[str] | None:
        record = await self.get_run(run_id)
        if not record:
            return None
        pubsub = self.redis.pubsub()
        try:
            await pubsub.subscribe(self._channel(run_id))
        except RedisError as exc:
            await pubsub.close()
            self._raise_redis_error("subscribe", exc)
        queue: asyncio.Queue[str] = asyncio.Queue()

        async def reader():
            try:
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    data = message.get("data")
                    if data is None:
                        continue
                    await queue.put(data)
            finally:
                try:
                    await pubsub.unsubscribe(self._channel(run_id))
                finally:
                    await pubsub.close()

        task = asyncio.create_task(reader())
        self._subscriber_tasks[queue] = task
        return queue

    async def unsubscribe(self, run_id: str, queue: asyncio.Queue[str]) -> None:
        task = self._subscriber_tasks.pop(queue, None)
        if task:
            task.cancel()
            with contextlib.suppress(Exception):
                await task

    async def publish(self, run_id: str, event_name: str, payload: dict[str, Any]) -> None:
        record = await self.get_run(run_id)
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
        await self._save_run(run_id, record)
        message = _sse_event(event_name, data)
        try:
            await self.redis.publish(self._channel(run_id), message)
        except RedisError as exc:
            self._raise_redis_error("publish", exc)

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
            record.tool_text += payload.get("delta", "")
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
        elif event_name == "summary.error":
            record.summary_ended = True
            modules["summary"]["answerStatus"] = "fail"
            modules["summary"]["error"] = payload
            if record.think_started:
                modules["summary"]["thinkStatus"] = "fail"
            record.result["content"] = record.summary_text
            record.result["reasoning"] = record.think_text
            record.result["raw"] = payload
            record.finished_at = payload.get("finishedAt") or int(time.time() * 1000)
            record.status = "FAIL"
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
            if record.tool_text and not record.result.get("toolSummary"):
                record.result["toolSummary"] = record.tool_text

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

        if event_name == "run.cancel":
            record.status = "CANCELLED"
            record.finished_at = payload.get("finishedAt") or int(time.time() * 1000)
            if not record.result.get("content"):
                record.result["content"] = record.summary_text
            if not record.result.get("reasoning"):
                record.result["reasoning"] = record.think_text
            if record.tool_text and not record.result.get("toolSummary"):
                record.result["toolSummary"] = record.tool_text
            modules["summary"]["answerStatus"] = "fail"

    async def _save_run(self, run_id: str, record: RunRecord) -> None:
        payload = json.dumps(record.to_dict(), ensure_ascii=False)
        try:
            await self.redis.set(self._key_record(run_id), payload, ex=self.ttl_seconds)
        except RedisError as exc:
            self._raise_redis_error("save_run", exc)


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
