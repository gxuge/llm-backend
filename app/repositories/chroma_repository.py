import json
from typing import Any
from uuid import uuid4

from fastapi import Depends

from app.core.chroma import collection_dependency


class ChromaRepository:
    def __init__(self, collection: Any) -> None:
        self.collection = collection

    def add_conversation_record(
        self,
        conversation_id: str,
        model: str,
        messages: list[dict[str, Any]],
        reply: str,
        reasoning: str | None,
    ) -> None:
        self.collection.add(
            ids=[f"{conversation_id}:{uuid4()}"],
            documents=[
                json.dumps(
                    {
                        "conversation_id": conversation_id,
                        "model": model,
                        "messages": messages,
                        "reply": reply,
                        "reasoning": reasoning,
                    },
                    ensure_ascii=False,
                )
            ],
            metadatas=[{"conversation_id": conversation_id, "model": model}],
        )

    def upsert_vector(
        self,
        *,
        vector_id: str,
        embedding: list[float],
        document: str | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        self.collection.upsert(
            ids=[vector_id],
            embeddings=[embedding],
            documents=[document],
            metadatas=[metadata],
        )

    def query_vectors(self, *, embedding: list[float], top_k: int) -> dict[str, Any]:
        return self.collection.query(query_embeddings=[embedding], n_results=top_k)


def chroma_repository_dependency(
    collection=Depends(collection_dependency),
) -> ChromaRepository:
    return ChromaRepository(collection)
