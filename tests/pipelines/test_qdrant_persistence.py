"""Embedded Qdrant must survive client close and must not use the runtime store in tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine

from shared.healthcore_rag.config import COLLECTION_NAME, VECTOR_SIZE
from shared.healthcore_rag.qdrant import (
    close_qdrant_client,
    get_qdrant_client,
    resolve_embedded_qdrant_path,
)


def test_embedded_index_survives_client_close(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A prepared collection remains on disk after close and is reopened without ingest."""
    store = tmp_path / "qdrant_storage"
    monkeypatch.setenv("QDRANT_PATH", str(store))
    monkeypatch.setattr("shared.healthcore_rag.config.QDRANT_PATH", str(store))
    monkeypatch.setattr(
        "data.process.rag.embed",
        lambda _text: [0.01] * VECTOR_SIZE,
    )
    close_qdrant_client()

    from data.process.rag import setup

    summary = setup()
    assert summary["collection"] == COLLECTION_NAME
    assert summary["chunk_count"] == 47
    sqlite_path = store / "collection" / COLLECTION_NAME / "storage.sqlite"
    assert sqlite_path.is_file()
    first_count = get_qdrant_client().count(COLLECTION_NAME).count
    assert first_count == 47

    close_qdrant_client()
    assert store.is_dir()
    assert sqlite_path.is_file()

    reopened = get_qdrant_client()
    assert reopened.collection_exists(COLLECTION_NAME)
    assert reopened.count(COLLECTION_NAME).count == 47
    close_qdrant_client()
    assert sqlite_path.is_file()


def test_foreign_monorepo_qdrant_path_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    foreign = tmp_path / "healthcore-i36-d37ac3a" / "data" / "process" / "qdrant_storage"
    monkeypatch.setattr("shared.healthcore_rag.config.QDRANT_PATH", str(foreign))
    monkeypatch.delenv("HEALTHCORE_ALLOW_EXTERNAL_QDRANT", raising=False)
    with pytest.raises(RuntimeError, match="outside this checkout"):
        resolve_embedded_qdrant_path(allow_pytest_override=False)


def test_intentional_external_qdrant_path_requires_explicit_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    external = tmp_path / "intentional_external_qdrant"
    monkeypatch.setattr("shared.healthcore_rag.config.QDRANT_PATH", str(external))
    monkeypatch.setenv("HEALTHCORE_ALLOW_EXTERNAL_QDRANT", "1")
    close_qdrant_client()

    assert resolve_embedded_qdrant_path(allow_pytest_override=False) == str(external.resolve())
    get_qdrant_client()
    close_qdrant_client()
    assert (external / "meta.json").is_file()


def test_close_qdrant_client_does_not_delete_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = tmp_path / "keep_me"
    monkeypatch.setenv("QDRANT_PATH", str(store))
    monkeypatch.setattr("shared.healthcore_rag.config.QDRANT_PATH", str(store))
    close_qdrant_client()
    get_qdrant_client()
    assert store.is_dir()
    close_qdrant_client()
    assert store.is_dir()
    assert (store / "meta.json").is_file()


def test_api_lifespan_closes_qdrant_without_deleting_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A graceful FastAPI shutdown releases the embedded store and preserves it."""
    store = tmp_path / "lifespan_store"
    monkeypatch.setattr("shared.healthcore_rag.config.QDRANT_PATH", str(store))
    close_qdrant_client()
    get_qdrant_client()
    assert (store / "meta.json").is_file()

    from app import main as api_main

    engine = create_engine(f"sqlite:///{(tmp_path / 'lifespan.db').as_posix()}")
    monkeypatch.setattr(api_main, "init_databases", lambda: None)
    monkeypatch.setattr(api_main, "get_engine", lambda: engine)
    monkeypatch.setattr(api_main, "seed_inventory_if_empty", lambda _session: None)
    monkeypatch.setattr(api_main, "ensure_demonstration_accounts", lambda _session: None)

    with TestClient(api_main.app) as client:
        assert client.get("/health").status_code == 200

    import shared.healthcore_rag.qdrant as qdrant_module

    assert qdrant_module._client is None
    assert store.is_dir()
    assert (store / "meta.json").is_file()
