"""Eager Celery tick against an owned store. Does not start or stop brokers."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
API_DIR = REPO / "services" / "api"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import pytest

from agents.supplier_contracts.runtime import ContractRuntime
from app.services.supplier_contracts_service import reset_runtime_for_tests


@pytest.fixture
def eager_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    process = tmp_path / "process"
    raw = tmp_path / "raw"
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "1")
    monkeypatch.setenv("SUPPLIER_CONTRACTS_PROCESS_DIR", str(process))
    monkeypatch.setenv("SUPPLIER_CONTRACTS_RAW_DIR", str(raw))
    monkeypatch.setenv("SECRET_KEY", "task4-worker-test-secret-key-32")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'worker.db').as_posix()}")
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "auth.json"))
    for name in ("GENERATION_API_KEY", "REDIS_URL", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    reset_runtime_for_tests()
    ContractRuntime(raw=raw, process=process).ensure_seeded()
    return process


def test_eager_tick_emits_internal_alerts(eager_env: Path) -> None:
    from app.tasks_supplier_contracts import tick_supplier_contract_alerts

    payload = tick_supplier_contract_alerts()
    assert "emitted" in str(payload.get("answer", "")).lower() or payload.get("alerts") is not None
    reset_runtime_for_tests()
