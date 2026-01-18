from __future__ import annotations

from functools import lru_cache

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from app.nodes.compute import compute_decider
from app.nodes.extract import extract_query
from app.nodes.planner import plan_tools
from app.nodes.rag import rag_retrieve
from app.nodes.router import route_tools
from app.nodes.state import AgentState
from app.nodes.synth import rag_summary, synth_final, tool_summary
from app.nodes.tool_node import tool_node
from app.nodes.viz import viz_builder


def _route_after_router(state: AgentState) -> str:
    return "need_tools" if state.get("need_tools") else "no_tools"


def _route_after_plan(state: AgentState) -> str:
    last_ai = next(
        (msg for msg in reversed(state.get("messages", [])) if isinstance(msg, AIMessage)),
        None,
    )
    if last_ai and last_ai.tool_calls:
        return "tools"
    return "done"


def _route_after_compute_decider(state: AgentState) -> str:
    return "compute" if state.get("need_compute") else "skip"


def build_exam_agent_graph() -> StateGraph:
    """src 布局下的图编排入口。"""
    graph = StateGraph(AgentState)
    graph.add_node("extract", extract_query)
    graph.add_node("retrieve", rag_retrieve)
    graph.add_node("router", route_tools)
    graph.add_node("rag_summary", rag_summary)
    graph.add_node("plan_tools", plan_tools)
    graph.add_node("tools", tool_node)
    graph.add_node("compute_decider", compute_decider)
    graph.add_node("tool_summary", tool_summary)
    graph.add_node("viz", viz_builder)
    graph.add_node("final", synth_final)

    graph.add_edge(START, "extract")
    graph.add_edge("extract", "retrieve")
    graph.add_edge("retrieve", "rag_summary")
    graph.add_edge("rag_summary", "router")
    graph.add_conditional_edges(
        "router",
        _route_after_router,
        {"need_tools": "plan_tools", "no_tools": "compute_decider"},
    )
    graph.add_conditional_edges(
        "plan_tools",
        _route_after_plan,
        {"tools": "tools", "done": "compute_decider"},
    )
    graph.add_edge("tools", "plan_tools")
    graph.add_conditional_edges(
        "compute_decider",
        _route_after_compute_decider,
        {"compute": "tools_compute", "skip": "viz"},
    )
    graph.add_node("tools_compute", tool_node)
    graph.add_edge("tools_compute", "viz")
    graph.add_edge("viz", "tool_summary")
    graph.add_edge("tool_summary", "final")
    graph.add_edge("final", END)
    return graph


@lru_cache(maxsize=1)
def get_exam_agent_graph():
    return build_exam_agent_graph().compile()
