from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.repositories.chroma_repository import chroma_repository_dependency

router = APIRouter(tags=["Chroma"])


class VectorPayload(BaseModel):
    id: str = Field(..., description="Unique vector id")
    embedding: list[float] = Field(..., description="Precomputed embedding values")
    document: str | None = Field(None, description="Optional raw text to store")
    metadata: dict[str, Any] | None = Field(
        None, description="Optional metadata filters (string key/values)"
    )


class QueryPayload(BaseModel):
    embedding: list[float] = Field(..., description="Embedding to search against")
    top_k: int = Field(3, gt=0, description="Number of matches to return")


@router.post("/vectors", summary="Upsert a vector into Chroma")
def upsert_vector(
    payload: VectorPayload, chroma_repo=Depends(chroma_repository_dependency)
) -> dict[str, str]:
    try:
        chroma_repo.upsert_vector(
            vector_id=payload.id,
            embedding=payload.embedding,
            document=payload.document,
            metadata=payload.metadata,
        )
    except Exception as exc:  # pragma: no cover - demo safety
        raise HTTPException(status_code=500, detail=f"Chroma upsert failed: {exc}")
    return {"id": payload.id}


@router.post("/vectors/query", summary="Query nearest neighbors")
def query_vectors(
    payload: QueryPayload, chroma_repo=Depends(chroma_repository_dependency)
) -> dict[str, Any]:
    try:
        result = chroma_repo.query_vectors(
            embedding=payload.embedding, top_k=payload.top_k
        )
    except Exception as exc:  # pragma: no cover - demo safety
        raise HTTPException(status_code=500, detail=f"Chroma query failed: {exc}")

    return {
        "ids": result.get("ids", []),
        "distances": result.get("distances", []),
        "documents": result.get("documents", []),
        "metadatas": result.get("metadatas", []),
    }
