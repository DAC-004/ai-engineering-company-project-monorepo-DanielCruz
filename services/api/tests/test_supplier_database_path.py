"""SUPPLIERS_DB_PATH resolution for isolated validation vs default store."""

from __future__ import annotations

import importlib
import os
from pathlib import Path


def _reload_supplier_database(monkeypatch, env_value: str | None) -> object:
    if env_value is None:
        monkeypatch.delenv("SUPPLIERS_DB_PATH", raising=False)
    else:
        monkeypatch.setenv("SUPPLIERS_DB_PATH", env_value)
    import app.database as supplier_database

    return importlib.reload(supplier_database)


def test_suppliers_db_path_uses_default_when_unset(monkeypatch):
    from shared.healthcore_rag.config import runtime_data_path

    module = _reload_supplier_database(monkeypatch, None)
    expected = runtime_data_path(
        Path("/var/lib/healthcore/suppliers/suppliers.json"),
        Path(__file__).resolve().parents[1] / "data" / "suppliers.json",
    )
    assert module.DB_PATH == expected


def test_suppliers_db_path_honors_explicit_override(monkeypatch, tmp_path: Path):
    override = tmp_path / "isolated-suppliers.json"
    module = _reload_supplier_database(monkeypatch, str(override))
    assert module.DB_PATH == override
