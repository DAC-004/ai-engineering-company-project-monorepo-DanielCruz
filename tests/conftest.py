"""Keep pytest off the runtime embedded Qdrant directory."""

from __future__ import annotations

import os

import pytest

from shared.healthcore_rag.qdrant import close_qdrant_client


def _use_runtime_qdrant() -> bool:
    return os.getenv("HEALTHCORE_USE_RUNTIME_QDRANT", "").strip() == "1" or os.getenv(
        "PART2_LIVE_RAG_EVAL", ""
    ).strip() == "1"


@pytest.fixture(autouse=True)
def isolate_embedded_qdrant(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Send non-live tests to a throwaway store so they cannot wipe the knowledge index."""
    close_qdrant_client()
    if _use_runtime_qdrant():
        yield
        close_qdrant_client()
        return

    isolated = tmp_path_factory.mktemp("qdrant")
    monkeypatch.setenv("QDRANT_PATH", str(isolated))
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.setattr("shared.healthcore_rag.config.QDRANT_PATH", str(isolated))
    monkeypatch.setattr("shared.healthcore_rag.config.QDRANT_URL", "")
    yield
    close_qdrant_client()
