from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from src.exam_agent.nodes.utils import split_dataset_ids
from src.exam_agent.schemas.types import Citation


async def ragflow_retrieve(question: str) -> tuple[list[str], list[Citation]]:
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
    items = (
        data.get("data")
        or data.get("chunks")
        or data.get("documents")
        or data.get("hits")
        or []
    )
    contexts: list[str] = []
    citations: list[Citation] = []
    for item in items:
        if isinstance(item, str):
            contexts.append(item)
            citations.append(Citation(snippet=item))
            continue
        if not isinstance(item, dict):
            continue
        text = item.get("content") or item.get("text") or item.get("chunk") or item.get("document")
        if text:
            contexts.append(text)
        citations.append(
            Citation(
                title=item.get("title"),
                source=item.get("source"),
                snippet=item.get("snippet") or text,
                url=item.get("url"),
            )
        )
    return contexts, citations
