from __future__ import annotations

from collections.abc import AsyncGenerator

from langchain_core.messages import HumanMessage

from src.agents.graphs.exam_agent_graph import get_exam_agent_graph
from src.app.services.run_store import _sse_event


# 非流式调用，便于内部复用或调试
async def run_agent(question: str, access_token: str | None = None) -> dict:
    graph = get_exam_agent_graph()
    initial_state = {
        "question": question,
        "messages": [HumanMessage(content=question)],
        "tool_round": 0,
        "access_token": access_token,
    }
    return await graph.invoke(initial_state)


# SSE 流式调用，输出 delta/data/chart/final 事件
def _extract_enable_think(sampling: dict | None) -> bool:
    if not sampling:
        return False
    return bool(sampling.get("enable_think") or sampling.get("enableThink"))


async def stream_agent(
    question: str,
    access_token: str | None = None,
    sampling: dict | None = None,
) -> AsyncGenerator[str, None]:
    graph = get_exam_agent_graph()
    enable_think = _extract_enable_think(sampling)
    initial_state = {
        "question": question,
        "messages": [HumanMessage(content=question)],
        "tool_round": 0,
        "access_token": access_token,
        "enable_think": enable_think,
        "show_think": enable_think,
    }
    async for chunk in graph.astream(initial_state, stream_mode="custom"):
        if isinstance(chunk, dict) and "event" in chunk:
            yield _sse_event(chunk["event"], chunk["data"])
        else:
            yield _sse_event("trace.event", {"message": str(chunk)})
