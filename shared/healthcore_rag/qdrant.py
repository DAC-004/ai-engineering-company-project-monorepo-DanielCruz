"""Qdrant client factory for HealthCore knowledge indexing and retrieval."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from qdrant_client import QdrantClient

from shared.healthcore_rag import config as rag_config

_client: QdrantClient | None = None
logger = logging.getLogger(__name__)


def resolve_embedded_qdrant_path(*, allow_pytest_override: bool = True) -> str:
    """Return the embedded storage path, refusing another checkout's store.

    A leftover `QDRANT_PATH` from a sibling worktree would index and retrieve
    against that tree while this clone appears empty. Pytest temp directories
    are allowed. Set `HEALTHCORE_ALLOW_EXTERNAL_QDRANT=1` only for an
    intentional store outside this repository.
    """
    raw = str(rag_config.QDRANT_PATH)
    if raw == ":memory:":
        return raw
    resolved = Path(raw).expanduser().resolve()
    repo = rag_config.REPO_ROOT.resolve()
    try:
        resolved.relative_to(repo)
        return str(resolved)
    except ValueError:
        pass
    if os.getenv("HEALTHCORE_ALLOW_EXTERNAL_QDRANT", "").strip() == "1":
        return str(resolved)
    if allow_pytest_override and os.getenv("PYTEST_CURRENT_TEST"):
        return str(resolved)
    raise RuntimeError(
        f"QDRANT_PATH {resolved} is outside this checkout, not "
        f"{repo / 'data' / 'process' / 'qdrant_storage'}. Unset QDRANT_PATH "
        "or point it inside this repository. Set "
        "HEALTHCORE_ALLOW_EXTERNAL_QDRANT=1 only for an intentional external "
        "store. This process will not use or convert a foreign knowledge store."
    )


def get_qdrant_client() -> QdrantClient:
    """Return a process-wide Qdrant client.

    Preference order:
    1. `QDRANT_URL` for Docker Compose or Qdrant Cloud
    2. `QDRANT_PATH=:memory:` for isolated tests
    3. Local embedded storage under `data/process/qdrant_storage`

    Path and URL are read at call time so tests can redirect storage without
    reloading this module. Opening the embedded path does not recreate or
    delete an existing index.
    """
    global _client
    if _client is not None:
        return _client

    if rag_config.QDRANT_URL:
        _client = QdrantClient(url=rag_config.QDRANT_URL, api_key=rag_config.QDRANT_API_KEY or None)
        return _client

    path = resolve_embedded_qdrant_path()
    if path == ":memory:":
        _client = QdrantClient(":memory:")
        return _client

    _client = QdrantClient(path=path)
    return _client


def close_qdrant_client() -> None:
    """Close the cached client so shutdown and tests release the storage lock.

    The embedded directory is left in place. Tests must point `QDRANT_PATH` at
    a disposable directory; they must not delete the runtime index.
    """
    global _client
    if _client is None:
        return
    try:
        _client.close()
    except Exception:
        logger.exception("Qdrant client close failed")
    finally:
        _client = None
