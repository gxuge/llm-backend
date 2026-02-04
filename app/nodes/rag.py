from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.langfuse import end_span, get_current_trace, start_span
from app.nodes.state import AgentState
from app.nodes.utils import split_dataset_ids
from app.schemas.exam_agent import Citation
from src.exam_agent.services.events import emit_event
import logging

logger = logging.getLogger(__name__)


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


async def _fastgpt_retrieve(question: str) -> tuple[list[str], list[Citation]]:
    """调用 FastGPT searchTest 接口进行检索。"""
    if not settings.fastgpt_api_base:
        raise ValueError("FastGPT api_base not configured.")
    if not settings.fastgpt_api_key:
        raise ValueError("FastGPT api_key not configured.")
    if not settings.fastgpt_dataset_id:
        raise ValueError("FastGPT dataset_id not configured.")
    url = settings.fastgpt_api_base.rstrip("/") + "/api/core/dataset/searchTest"
    headers = {"Authorization": f"Bearer {settings.fastgpt_api_key}"}
    payload: dict[str, Any] = {
        "datasetId": settings.fastgpt_dataset_id,
        "text": question,
        "limit": 5000,
        "similarity": 0.3,
        "searchMode": "embedding",
        "usingReRank": True,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=headers)
    if response.status_code >= 400:
        raise ValueError(f"FastGPT error {response.status_code}: {response.text}")
    data = response.json()
    data_block = data.get("data") if isinstance(data, dict) else {}
    if not isinstance(data_block, dict):
        data_block = {}
    items = data_block.get("list") or []
    if not isinstance(items, list):
        items = []
    top_k = max(1, int(settings.fastgpt_top_k_default or 4))
    items = items[:top_k]
    contexts: list[str] = []
    citations: list[Citation] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        answer = item.get("a") or ""
        question_text = item.get("q") or ""
        snippet = answer or question_text
        if snippet:
            contexts.append(snippet)
        citations.append(
            Citation(
                title=item.get("sourceName"),
                source=item.get("sourceId") or item.get("collectionId"),
                snippet=snippet or None,
                url=None,
            )
        )
    return contexts, citations


async def rag_retrieve(state: AgentState) -> AgentState:
    """RAG 主流程：检索 + 事件上报。"""
    question = state["question"]
    emit_event(state, "rag.start", {"question": question}, status="running", step_id="rag")
    trace = get_current_trace()
    span = start_span(trace, name="node.rag_retrieve", input_data={"question": question})
    error_message: str | None = None
    try:
        provider = (settings.rag_provider or "ragflow").lower()
        if provider == "fastgpt":
            contexts, citations = await _fastgpt_retrieve(question)
        else:
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
        error_message = str(exc)
        emit_event(
            state,
            "rag.error",
            {"message": str(exc)},
            status="failed",
            step_id="rag",
        )
    end_span(
        span,
        output={"context_count": len(contexts), "citation_count": len(citations)},
        metadata={"error": error_message} if error_message else None,
    )
    return {"policy_context": contexts, "citations": citations}
