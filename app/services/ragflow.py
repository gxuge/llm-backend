import json
import logging
from functools import lru_cache
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class RagflowConfigError(Exception):
    """Raised when RAGFlow configuration is missing."""


class RagflowRetrievalError(Exception):
    """Raised when RAGFlow retrieval fails."""


class RagflowClient:
    """
    Minimal async client for querying a RAGFlow knowledge base.
    """

    RETRIEVAL_PATH = "/v1/knowledge_base/retrieval"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        kb_id: str | None,
        top_k_default: int,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.kb_id = kb_id
        self.top_k_default = top_k_default

    def _extract_contexts(self, payload: dict[str, Any]) -> list[str]:
        candidates = (
            payload.get("data")
            or payload.get("documents")
            or payload.get("hits")
            or payload.get("chunks")
            or []
        )
        contexts: list[str] = []
        for item in candidates:
            if isinstance(item, str):
                contexts.append(item)
                continue
            if isinstance(item, dict):
                text = (
                    item.get("content")
                    or item.get("text")
                    or item.get("document")
                    or item.get("chunk")
                )
                if text:
                    contexts.append(text)
        return contexts

    async def retrieve(self, query: str, *, top_k: int | None = None) -> list[str]:
        url = f"{self.base_url}{self.RETRIEVAL_PATH}"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {"query": query, "top_k": top_k or self.top_k_default}
        if self.kb_id:
            payload["kb_id"] = self.kb_id

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code >= 400:
            raise RagflowRetrievalError(
                f"RAGFlow responded with {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:  # pragma: no cover
            raise RagflowRetrievalError(f"RAGFlow response is not JSON: {exc}") from exc

        contexts = self._extract_contexts(data)
        if not contexts:
            raise RagflowRetrievalError("RAGFlow response did not contain retrievable text.")

        return contexts


@lru_cache()
def get_ragflow_client() -> RagflowClient:
    if not settings.ragflow_api_base:
        raise RagflowConfigError("APP_RAGFLOW_API_BASE is not configured.")
    if not settings.ragflow_api_key:
        raise RagflowConfigError("APP_RAGFLOW_API_KEY is not configured.")

    return RagflowClient(
        base_url=settings.ragflow_api_base,
        api_key=settings.ragflow_api_key,
        kb_id=settings.ragflow_kb_id,
        top_k_default=settings.ragflow_top_k_default,
    )
