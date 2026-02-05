from __future__ import annotations

import asyncio
import json
import time
import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.app.core.langfuse import flush_langfuse, set_current_trace, start_trace
from src.app.services.run_store import RedisUnavailableError, RunRecord, run_store
from src.app.workflows.default_agent import stream_default_agent
from src.app.workflows.sz_exam_agent import stream_agent

router = APIRouter(tags=["InternalRuns"])
logger = logging.getLogger(__name__)
RUN_TASKS: dict[str, asyncio.Task] = {}


class RunRequest(BaseModel):
    """内部运行请求体。"""

    userId: str = Field(..., description="User id for audit/isolation")
    sessionRole: Literal["planner", "default"] = Field(..., description="Session role: planner or default")
    sessionId: str | None = None
    topicId: str | None = None
    messageId: str | None = None
    conversationId: str | None = None
    input: str = Field(..., description="User input")
    messages: list[dict[str, Any]] | None = None
    model: str | None = None
    stream: bool = True
    clientId: str | None = None
    sampling: dict[str, Any] | None = None
    accessToken: str | None = None


class RunStartResponse(BaseModel):
    """启动运行响应。"""

    runId: str
    status: str
    startedAt: int
    traceId: str | None = None


# 解析 sse_event 产生的文本块，提取 event/data
def _parse_sse_event(raw: str) -> tuple[str | None, dict[str, Any] | None]:
    blocks = [block for block in raw.split("\n\n") if block.strip()]
    for block in blocks:
        event_name = None
        data_lines = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if not data_lines:
            continue
        data_text = "\n".join(data_lines)
        try:
            payload = json.loads(data_text)
        except json.JSONDecodeError:
            payload = {"text": data_text}
        return event_name, payload
    return None, None


CANONICAL_EVENTS = {
    "run.start",
    "run.end",
    "run.error",
    "rag.start",
    "rag.hits",
    "rag.summary.start",
    "rag.summary.delta",
    "rag.summary.end",
    "rag.end",
    "rag.error",
    "tool.call",
    "tool.start",
    "tool.result",
    "tool.error",
    "tool.summary.start",
    "tool.summary.delta",
    "tool.summary.end",
    "tool.end",
    "summary.think.start",
    "summary.think.delta",
    "summary.think.end",
    "summary.start",
    "summary.delta",
    "summary.error",
    "summary.end",
    "viz.table",
    "trace.event",
    "status",
}


def _strip_meta(payload: dict[str, Any]) -> dict[str, Any]:
    meta_keys = {"v", "run_id", "ts", "sequence_number", "status", "step_id", "parent_id", "group_id"}
    return {key: value for key, value in payload.items() if key not in meta_keys}


def _map_event(event_name: str, payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """将工作流侧的 SSE 事件映射为内部通用事件。"""
    mapped: list[tuple[str, dict[str, Any]]] = []
    # 表格事件：Python 端直接定义，透传 payload 即可
    if event_name.startswith("table."):
        clean = _strip_meta(payload) if isinstance(payload, dict) else {"data": payload}
        return [(event_name, clean)]
    if event_name in CANONICAL_EVENTS:
        clean = _strip_meta(payload) if isinstance(payload, dict) else {"data": payload}
        if event_name == "run.start":
            return [(event_name, clean)]
        if event_name.endswith(".delta"):
            delta_value = clean.get("delta") or clean.get("text") or clean.get("content") or ""
            return [(event_name, {"delta": delta_value})]
        if event_name == "summary.end":
            if "answer" not in clean and "text" in clean:
                clean["answer"] = clean.get("text")
            clean.setdefault("ok", True)
            return [(event_name, clean)]
        if event_name == "run.end":
            status = clean.get("status")
            ok = clean.get("ok")
            if ok is None and isinstance(status, str):
                ok = status.lower() in ("ok", "success", "succeeded")
            if ok is None:
                ok = True
            return [
                (
                    "run.end",
                    {
                        "ok": ok,
                        "finishedAt": clean.get("finishedAt") or int(time.time() * 1000),
                        "tokens": clean.get("tokens") or {"prompt": None, "completion": None, "total": None},
                    },
                )
            ]
        if event_name == "run.error":
            return [
                (
                    "run.error",
                    {
                        "message": clean.get("message"),
                        "code": clean.get("code") or "PY_RUN_ERROR",
                        "stack": clean.get("stack"),
                    },
                )
            ]
        return [(event_name, clean)]
    if event_name == "delta":
        text_value = None
        if isinstance(payload, dict):
            text_value = payload.get("delta") or payload.get("text")
        if text_value is None:
            text_value = str(payload)
        mapped.append(("summary.delta", {"delta": text_value}))
        return mapped
    if event_name == "data":
        if isinstance(payload, dict) and "columns" in payload and "rows" in payload:
            mapped.append(("viz.table", {"columns": payload.get("columns"), "rows": payload.get("rows")}))
        else:
            mapped.append(("viz.table", {"data": payload}))
        return mapped
    if event_name == "chart":
        mapped.append(("viz.chart", {"spec": payload}))
        return mapped
    if event_name == "final":
        text_value = None
        if isinstance(payload, dict):
            text_value = payload.get("text") or payload.get("answer")
        if text_value is None:
            text_value = str(payload)
        mapped.append(("summary.end", {"ok": True, "answer": text_value}))
        mapped.append(("run.end", {"ok": True, "finishedAt": int(time.time() * 1000), "tokens": {"prompt": None, "completion": None, "total": None}}))
        return mapped
    if event_name == "error":
        if isinstance(payload, dict):
            mapped.append(
                (
                    "run.error",
                    {"message": payload.get("message"), "code": payload.get("code") or "PY_RUN_ERROR", "stack": payload.get("stack")},
                )
            )
        else:
            mapped.append(("run.error", {"message": str(payload), "code": "PY_RUN_ERROR", "stack": None}))
        return mapped
    mapped.append(("trace.event", {"data": payload}))
    return mapped


async def _execute_run(run_id: str, payload: RunRequest) -> None:
    """执行工作流并把事件转换、发布到内部通道。"""

    summary_started = False
    summary_ended = False
    run_ended = False
    tool_started = False
    saw_think_start = False
    saw_think_delta = False
    saw_think_end = False
    rag_error_payload: dict[str, Any] | None = None
    tool_error_payload: dict[str, Any] | None = None
    summary_error_payload: dict[str, Any] | None = None
    summary_error_sent = False
    trace = start_trace(
        trace_id=payload.sessionId,
        session_id=payload.sessionId,
        user_id=payload.userId,
        name=f"exam.{payload.sessionRole}",
        metadata={"run_id": run_id, "session_role": payload.sessionRole},
    )
    set_current_trace(trace)
    try:
        record = await run_store.get_run(run_id)
        trace_id = record.trace_id if record else None
        await run_store.publish(
            run_id,
            "run.start",
            {"runId": run_id, "traceId": trace_id},
        )
        if payload.sessionRole == "default":
            stream = stream_default_agent(
                input_text=payload.input,
                messages=payload.messages,
                model=payload.model,
                sampling=payload.sampling,
            )
        else:
            stream = stream_agent(payload.input, access_token=payload.accessToken, sampling=payload.sampling)
        async for chunk in stream:
            block = chunk.strip()
            if not block:
                continue
            event_name, data = _parse_sse_event(block)
            if not event_name or data is None:
                continue
            for mapped_name, mapped_payload in _map_event(event_name, data):
                if mapped_name == "run.end":
                    continue
                if mapped_name == "rag.error":
                    if rag_error_payload is None and isinstance(mapped_payload, dict):
                        rag_error_payload = mapped_payload
                    continue
                if mapped_name == "tool.error":
                    if tool_error_payload is None and isinstance(mapped_payload, dict):
                        tool_error_payload = mapped_payload
                    continue
                if mapped_name == "summary.error":
                    if summary_error_payload is None and isinstance(mapped_payload, dict):
                        summary_error_payload = mapped_payload
                    continue
                if mapped_name == "summary.think.start":
                    saw_think_start = True
                elif mapped_name == "summary.think.delta":
                    saw_think_delta = True
                elif mapped_name == "summary.think.end":
                    saw_think_end = True

                if rag_error_payload:
                    if mapped_name == "rag.summary.end":
                        continue
                    if mapped_name == "rag.end":
                        await run_store.publish(run_id, "rag.error", rag_error_payload)
                        rag_error_payload = None
                        continue

                if tool_error_payload:
                    if mapped_name == "tool.summary.end":
                        continue
                    if mapped_name == "tool.end":
                        await run_store.publish(run_id, "tool.error", tool_error_payload)
                        tool_error_payload = None
                        continue

                if summary_error_payload and not summary_error_sent:
                    if mapped_name == "summary.think.end":
                        continue
                    if mapped_name == "summary.end":
                        await run_store.publish(run_id, "summary.error", summary_error_payload)
                        summary_error_sent = True
                        summary_ended = True
                        continue

                if mapped_name == "summary.start":
                    if summary_started:
                        continue
                    summary_started = True
                    await run_store.publish(run_id, mapped_name, mapped_payload)
                    continue

                if mapped_name.startswith("tool."):
                    if mapped_name == "tool.start":
                        if tool_started:
                            continue
                        tool_started = True
                        await run_store.publish(run_id, mapped_name, mapped_payload)
                        continue
                    if not tool_started:
                        tool_started = True
                    await run_store.publish(run_id, mapped_name, mapped_payload)
                    continue

                if mapped_name.startswith("summary.") and mapped_name not in {
                    "summary.start",
                    "summary.think.start",
                    "summary.think.delta",
                    "summary.think.end",
                }:
                    if not summary_started:
                        await run_store.publish(run_id, "summary.start", {"ok": True})
                        summary_started = True

                if mapped_name == "summary.end":
                    if (
                        (saw_think_start or saw_think_delta)
                        and not saw_think_end
                        and not summary_error_payload
                        and not summary_error_sent
                    ):
                        await run_store.publish(run_id, "summary.think.end", {})
                        saw_think_end = True
                await run_store.publish(run_id, mapped_name, mapped_payload)
                if mapped_name == "summary.end":
                    summary_ended = True
        if not summary_ended:
            record = await run_store.get_run(run_id)
            answer_text = record.summary_text if record else ""
            if (saw_think_start or saw_think_delta) and not saw_think_end:
                await run_store.publish(run_id, "summary.think.end", {})
                saw_think_end = True
            if not summary_started:
                await run_store.publish(run_id, "summary.start", {"ok": True})
                summary_started = True
            await run_store.publish(run_id, "summary.end", {"ok": True, "answer": answer_text})
        if not run_ended:
            if (saw_think_start or saw_think_delta) and not saw_think_end:
                await run_store.publish(run_id, "summary.think.end", {})
                saw_think_end = True
            await run_store.publish(
                run_id,
                "run.end",
                {
                    "ok": True,
                    "finishedAt": int(time.time() * 1000),
                    "tokens": {"prompt": None, "completion": None, "total": None},
                },
            )
            run_ended = True
    except asyncio.CancelledError:
        await run_store.publish(
            run_id,
            "run.cancel",
            {
                "ok": False,
                "reason": "cancelled",
                "finishedAt": int(time.time() * 1000),
                "tokens": {"prompt": None, "completion": None, "total": None},
            },
        )
        return
    except RedisUnavailableError:
        logger.error("Redis unavailable during run execution")
        return
    except Exception as exc:
        await run_store.publish(
            run_id,
            "run.error",
            {"message": str(exc), "code": "PY_RUN_EXCEPTION", "stack": None},
        )
    finally:
        set_current_trace(None)
        flush_langfuse()


@router.post("/internal/runs", response_model=RunStartResponse)
async def start_run(payload: RunRequest) -> RunStartResponse:
    """启动一次 run（快速返回，后台异步执行）。"""

    try:
        payload_dict = payload.dict()
    except Exception:
        payload_dict = payload.model_dump()
    if "accessToken" in payload_dict:
        payload_dict["accessToken"] = "***"
    logger.info("internal_runs payload=%s", json.dumps(payload_dict, ensure_ascii=False))

    if not payload.userId or not payload.input or not payload.sessionId or not payload.messageId or not payload.sessionRole:
        raise HTTPException(status_code=400, detail="missing required fields")
    run_id, record = await run_store.create_run(payload.userId, payload.clientId)
    task = asyncio.create_task(_execute_run(run_id, payload))
    RUN_TASKS[run_id] = task
    task.add_done_callback(lambda _task: RUN_TASKS.pop(run_id, None))
    return RunStartResponse(runId=run_id, status="RUNNING", startedAt=record.started_at, traceId=record.trace_id)


@router.post("/internal/runs/cancel")
async def cancel_run(runId: str = Query(..., alias="runId")) -> dict[str, Any]:
    """取消指定 run，触发任务终止并返回 run.end。"""

    task = RUN_TASKS.get(runId)
    if not task:
        raise HTTPException(status_code=404, detail="runId not found or already finished")
    task.cancel()
    return {"ok": True, "runId": runId}

@router.get("/internal/runs/events")
async def stream_events(runId: str = Query(..., alias="runId")) -> StreamingResponse:
    """订阅指定 run 的 SSE 事件流。"""

    queue = await run_store.subscribe(runId)
    if not queue:
        raise HTTPException(status_code=404, detail="runId not found")

    async def event_stream():
        try:
            while True:
                message = await queue.get()
                yield message
        finally:
            await run_store.unsubscribe(runId, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/internal/runs/result")
async def run_result(runId: str = Query(..., alias="runId")) -> dict[str, Any]:
    """获取 run 的最终结果与模块汇总。"""

    record = await run_store.get_run(runId)
    if not record:
        raise HTTPException(status_code=404, detail="runId not found")
    return {
        "protocolVersion": "1.0",
        "runId": runId,
        "status": record.status,
        "content": record.result.get("content"),
        "reasoning": record.result.get("reasoning"),
        "raw": record.result.get("raw"),
        "error": record.error,
        "finishedAt": record.finished_at,
        "modules": record.module_summary,
    }
