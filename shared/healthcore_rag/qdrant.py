"""Qdrant client factory for HealthCore knowledge indexing and retrieval."""

from __future__ import annotations

from qdrant_client import QdrantClient

from shared.healthcore_rag.config import QDRANT_API_KEY, QDRANT_PATH, QDRANT_URL

_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Return a process-wide Qdrant client.

    Preference order:
    1. `QDRANT_URL` for Docker Compose or Qdrant Cloud
    2. `QDRANT_PATH=:memory:` for isolated tests
    3. Local embedded storage under `data/process/qdrant_storage`
    """
    global _client
    if _client is not None:
        return _client

    if QDRANT_URL:
        _client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
        return _client

    if QDRANT_PATH == ":memory:":
        _client = QdrantClient(":memory:")
        return _client

    _client = QdrantClient(path=QDRANT_PATH)
    return _client


def close_qdrant_client() -> None:
    """Close the cached client so tests can swap storage backends."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
