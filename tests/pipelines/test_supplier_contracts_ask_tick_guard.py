"""Employee readers cannot enqueue the worker tick through /ask."""

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
from fastapi.testclient import TestClient

PASSWORD = "Task4Pass1"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("SECRET_KEY", "task4-api-test-secret-key-32")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setenv("SUPPLIERS_DB_PATH", str(tmp_path / "suppliers.json"))
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "1")
    monkeypatch.setenv("SUPPLIER_CONTRACTS_PROCESS_DIR", str(tmp_path / "process"))
    monkeypatch.setenv("SUPPLIER_CONTRACTS_RAW_DIR", str(tmp_path / "raw"))
    for name in ("GENERATION_API_KEY", "GENERATION_API_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "REDIS_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        "agents.supplier_contracts.generation.configured_transport",
        lambda messages: '{"kind":"evaluate_increase","tools":["consult_pricing"]}',
    )
    from app.core.config import get_settings
    from app.db.database import reset_engine_for_tests
    from app.db.tinydb import reset_db_for_tests
    from app.main import app
    from app.schemas.user import UserCreate, UserRole
    from app.services import user_service
    from app.services.supplier_contracts_service import reset_runtime_for_tests

    get_settings.cache_clear()
    reset_db_for_tests()
    reset_engine_for_tests()
    reset_runtime_for_tests()
    user_service.create_user(
        UserCreate(email="ops.employee@healthcore.example", password=PASSWORD),
        role=UserRole.employee,
        department_id="clinical_operations",
    )
    with TestClient(app) as test_client:
        yield test_client
    reset_runtime_for_tests()


def _login(client: TestClient) -> dict[str, str]:
    login = client.post("/auth/login", data={"username": "ops.employee@healthcore.example", "password": PASSWORD})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_employee_cannot_select_tick_alerts_on_ask(client: TestClient) -> None:
    headers = _login(client)
    response = client.post(
        "/supplier-contracts/ask",
        headers=headers,
        json={"kind": "tick_alerts", "question": "tick", "supplier_id": "HC-S01"},
    )
    assert response.status_code == 422


def test_employee_cannot_post_tick_endpoint(client: TestClient) -> None:
    headers = _login(client)
    response = client.post("/supplier-contracts/tick", headers=headers)
    assert response.status_code == 403
