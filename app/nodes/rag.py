from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.nodes.state import AgentState
from app.nodes.utils import split_dataset_ids
from app.schemas.exam_agent import Citation
from src.exam_agent.services.events import emit_event


async def _ragflow_retrieve(question: str) -> tuple[list[str], list[Citation]]:
    """调用 RAGFlow retrieval，返回上下文与引用。"""
    if not settings.ragflow_api_base:
        raise ValueError("RAGFlow base_url not configured.")
    if not settings.ragflow_api_key:
        raise ValueError("RAGFlow api_key not configured.")
    url = settings.ragflow_api_base.rstrip("/") + "/v1/retrieval"
    dataset_ids = split_dataset_ids(getattr(settings, "ragflow_dataset_ids", ""))
    if not dataset_ids and settings.ragflow_kb_id:
        dataset_ids = [settings.ragflow_kb_id]
    payload: dict[str, Any] = {"question": question, "dataset_ids": dataset_ids}
    rerank_id = getattr(settings, "ragflow_rerank_id", None)
    if rerank_id:
        payload["rerank_id"] = rerank_id
    headers = {"Authorization": f"Bearer {settings.ragflow_api_key}"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=headers)
    if response.status_code >= 400:
        raise ValueError(f"RAGFlow error {response.status_code}: {response.text}")
    data = response.json()
    data_block = data.get("data") if isinstance(data, dict) else None
    if isinstance(data_block, dict):
        items = (
            data_block.get("chunks")
            or data_block.get("documents")
            or data_block.get("hits")
            or []
        )
        doc_aggs = data_block.get("doc_aggs") or []
    else:
        items = (
            data.get("chunks")
            or data.get("documents")
            or data.get("hits")
            or []
        )
        doc_aggs = data.get("doc_aggs") if isinstance(data, dict) else []
    doc_name_map: dict[str, str] = {}
    if isinstance(doc_aggs, list):
        for agg in doc_aggs:
            if not isinstance(agg, dict):
                continue
            doc_id = agg.get("doc_id") or agg.get("document_id")
            doc_name = agg.get("doc_name") or agg.get("document_keyword")
            if doc_id and doc_name:
                doc_name_map[str(doc_id)] = str(doc_name)
    contexts: list[str] = []
    citations: list[Citation] = []
    for item in items:
        if isinstance(item, str):
            contexts.append(item)
            citations.append(Citation(snippet=item))
            continue
        if not isinstance(item, dict):
            continue
        doc_id = item.get("document_id") or item.get("doc_id")
        doc_title = doc_name_map.get(str(doc_id)) if doc_id is not None else None
        text = item.get("content") or item.get("text") or item.get("chunk") or item.get("document")
        highlight = item.get("highlight")
        if text:
            contexts.append(text)
        citations.append(
            Citation(
                title=item.get("title") or doc_title,
                source=item.get("source") or item.get("document_keyword") or doc_id,
                snippet=item.get("snippet") or highlight or text,
                url=item.get("url"),
            )
        )
    return contexts, citations


async def rag_retrieve(state: AgentState) -> AgentState:
    """RAG 主流程：检索 + 事件上报。"""
    question = state["question"]
    emit_event(state, "rag.start", {"question": question}, status="running", step_id="rag")
    try:
        contexts, citations = await _ragflow_retrieve(question)
        emit_event(
            state,
            "rag.hits",
            {
                "hits": [c.model_dump() for c in citations],
                "count": len(citations),
                "context_count": len(contexts),
            },
            status="running",
            step_id="rag",
        )
    except Exception as exc:
        contexts, citations = [], []
        emit_event(
            state,
            "rag.error",
            {"message": str(exc)},
            status="failed",
            step_id="rag",
        )
    return {"policy_context": contexts, "citations": citations}
