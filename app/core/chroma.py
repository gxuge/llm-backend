from functools import lru_cache

import chromadb
from chromadb.api import ClientAPI

from app.core.config import settings


@lru_cache()
def get_persistent_client() -> ClientAPI:
    """
    Always use the local persistent store to avoid HTTP 502s when no Chroma
    server is running.
    """
    return chromadb.PersistentClient(path=settings.chroma_persist_path)


def collection_dependency():
    """
    FastAPI dependency wrapper so routers can `Depends` on a Chroma collection.
    """
    client = get_persistent_client()
    return client.get_or_create_collection(settings.chroma_collection)
