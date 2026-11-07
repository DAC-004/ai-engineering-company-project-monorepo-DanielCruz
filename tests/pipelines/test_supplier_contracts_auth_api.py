"""API identity matrix. Isolated stores; fake transport; no live provider."""

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

from agents.supplier_contracts.approvals import create_draft
from app.schemas.user import UserCreate, UserRole, UserUpdate
from app.services import user_service
from app.services.supplier_contracts_service import reset_runtime_for_tests, runtime

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

    get_settings.cache_clear()
    reset_db_for_tests()
    reset_engine_for_tests()
    reset_runtime_for_tests()
    with TestClient(app) as test_client:
        yield test_client
    reset_runtime_for_tests()


def _login(client: TestClient, email: str) -> dict[str, str]:
    login = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _user(*, email: str, role: UserRole, department_id: str | None) -> None:
    user_service.create_user(UserCreate(email=email, password=PASSWORD), role=role, department_id=department_id)


def test_employee_cannot_approve(client: TestClient) -> None:
    _user(email="marcus.clinical@healthcore.example", role=UserRole.employee, department_id="clinical_operations")
    headers = _login(client, "marcus.clinical@healthcore.example")
    response = client.post(
        "/supplier-contracts/approvals",
        headers=headers,
        json={"draft_id": "x", "version": 1, "content_sha256": "a" * 64, "approval_nonce": "b" * 32},
    )
    assert response.status_code == 403


def test_unrelated_department_cannot_read_registry(client: TestClient) -> None:
    _user(email="people.supervisor@healthcore.example", role=UserRole.supervisor, department_id="people_workforce")
    headers = _login(client, "people.supervisor@healthcore.example")
    response = client.get("/supplier-contracts/registry", headers=headers)
    assert response.status_code == 403


def test_missing_department_cannot_approve(client: TestClient, tmp_path: Path) -> None:
    created = user_service.create_user(
        UserCreate(email="marcus.clinical@healthcore.example", password=PASSWORD),
        role=UserRole.supervisor,
        department_id="clinical_operations",
    )
    user_service.update_user(created.id, UserUpdate(department_id=None))
    draft = create_draft(runtime().store, supplier_id="HC-S07", kind="draft_communication", body="internal")
    headers = _login(client, "marcus.clinical@healthcore.example")
    response = client.post(
        "/supplier-contracts/approvals",
        headers=headers,
        json={
            "draft_id": draft["draft_id"],
            "version": draft["version"],
            "content_sha256": draft["content_sha256"],
            "approval_nonce": draft["approval_nonce"],
        },
    )
    assert response.status_code == 403


def test_wrong_named_identity_cannot_approve(client: TestClient) -> None:
    _user(email="ops.supervisor@healthcore.example", role=UserRole.supervisor, department_id="clinical_operations")
    draft = create_draft(runtime().store, supplier_id="HC-S07", kind="draft_communication", body="internal")
    headers = _login(client, "ops.supervisor@healthcore.example")
    response = client.post(
        "/supplier-contracts/approvals",
        headers=headers,
        json={
            "draft_id": draft["draft_id"],
            "version": draft["version"],
            "content_sha256": draft["content_sha256"],
            "approval_nonce": draft["approval_nonce"],
        },
    )
    assert response.status_code == 403


def test_inactive_account_cannot_authenticate(client: TestClient) -> None:
    created = user_service.create_user(
        UserCreate(email="marcus.clinical@healthcore.example", password=PASSWORD),
        role=UserRole.supervisor,
        department_id="clinical_operations",
    )
    user_service.update_user(created.id, UserUpdate(is_active=False))
    login = client.post(
        "/auth/login",
        data={"username": "marcus.clinical@healthcore.example", "password": PASSWORD},
    )
    assert login.status_code == 401


def test_payload_impersonation_is_rejected(client: TestClient) -> None:
    _user(email="ops.supervisor@healthcore.example", role=UserRole.supervisor, department_id="clinical_operations")
    headers = _login(client, "ops.supervisor@healthcore.example")
    response = client.post(
        "/supplier-contracts/approvals",
        headers=headers,
        json={
            "draft_id": "x",
            "version": 1,
            "content_sha256": "a" * 64,
            "approval_nonce": "b" * 32,
            "email": "marcus.clinical@healthcore.example",
            "approver": "marcus.reid",
        },
    )
    assert response.status_code == 422


def test_clinical_supervisor_can_read_registry(client: TestClient) -> None:
    _user(email="marcus.clinical@healthcore.example", role=UserRole.supervisor, department_id="clinical_operations")
    headers = _login(client, "marcus.clinical@healthcore.example")
    response = client.get("/supplier-contracts/registry", headers=headers)
    assert response.status_code == 200
    assert any(item["supplier_id"] == "HC-S04" and item["display_name"] == "Lone Star Diagnostics" for item in response.json())


def _seed_named_approvers() -> None:
    _user(email="marcus.clinical@healthcore.example", role=UserRole.supervisor, department_id="clinical_operations")
    _user(email="claire.compliance@healthcore.example", role=UserRole.supervisor, department_id="compliance")
    _user(email="sandra.executive@healthcore.example", role=UserRole.admin, department_id="technology")


def test_required_approvers_retrieve_the_same_persisted_draft_after_refresh(client: TestClient) -> None:
    _seed_named_approvers()
    draft = create_draft(runtime().store, supplier_id="HC-S07", kind="draft_communication", body="internal-s07")
    marcus = _login(client, "marcus.clinical@healthcore.example")
    first = client.get("/supplier-contracts/drafts", headers=marcus)
    second = client.get(f"/supplier-contracts/drafts/{draft['draft_id']}", headers=marcus)
    assert first.status_code == 200
    assert second.status_code == 200
    listed = first.json()
    assert len(listed) == 1
    assert listed[0]["draft_id"] == draft["draft_id"]
    assert listed[0]["body"] == "internal-s07"
    assert listed[0]["draft_id"] == second.json()["draft_id"]
    assert listed[0]["content_sha256"] == second.json()["content_sha256"]
    claire = _login(client, "claire.compliance@healthcore.example")
    retrieved = client.get(f"/supplier-contracts/drafts/{draft['draft_id']}", headers=claire)
    assert retrieved.status_code == 200
    assert retrieved.json()["draft_id"] == draft["draft_id"]
    assert retrieved.json()["body"] == "internal-s07"


def test_employee_and_unrelated_actors_cannot_read_named_drafts(client: TestClient) -> None:
    _seed_named_approvers()
    _user(email="task4.employee@healthcore.example", role=UserRole.employee, department_id="clinical_operations")
    _user(email="ops.supervisor@healthcore.example", role=UserRole.supervisor, department_id="clinical_operations")
    _user(email="people.supervisor@healthcore.example", role=UserRole.supervisor, department_id="people_workforce")
    draft = create_draft(runtime().store, supplier_id="HC-S07", kind="draft_communication", body="internal-s07")
    employee = _login(client, "task4.employee@healthcore.example")
    listed = client.get("/supplier-contracts/drafts", headers=employee)
    missing = client.get(f"/supplier-contracts/drafts/{draft['draft_id']}", headers=employee)
    assert listed.status_code == 200
    assert listed.json() == []
    assert missing.status_code == 404
    wrong_name = _login(client, "ops.supervisor@healthcore.example")
    assert client.get("/supplier-contracts/drafts", headers=wrong_name).json() == []
    assert client.get(f"/supplier-contracts/drafts/{draft['draft_id']}", headers=wrong_name).status_code == 404
    unrelated = _login(client, "people.supervisor@healthcore.example")
    assert client.get("/supplier-contracts/drafts", headers=unrelated).status_code == 403
    claire_only = create_draft(runtime().store, supplier_id="HC-S01", kind="draft_communication", body="internal-s01")
    claire = _login(client, "claire.compliance@healthcore.example")
    assert client.get(f"/supplier-contracts/drafts/{claire_only['draft_id']}", headers=claire).status_code == 404


def test_named_approvers_grant_the_same_draft_after_login_switch(client: TestClient) -> None:
    _seed_named_approvers()
    draft = create_draft(runtime().store, supplier_id="HC-S07", kind="draft_communication", body="internal-s07")
    marcus = _login(client, "marcus.clinical@healthcore.example")
    first = client.post(
        "/supplier-contracts/approvals",
        headers=marcus,
        json={
            "draft_id": draft["draft_id"],
            "version": draft["version"],
            "content_sha256": draft["content_sha256"],
            "approval_nonce": draft["approval_nonce"],
        },
    )
    assert first.status_code == 200
    assert "marcus.reid" in first.json()["granted"]
    assert first.json()["state"] == "pending"
    claire = _login(client, "claire.compliance@healthcore.example")
    refreshed = client.get(f"/supplier-contracts/drafts/{draft['draft_id']}", headers=claire)
    assert refreshed.status_code == 200
    current = refreshed.json()
    assert current["draft_id"] == draft["draft_id"]
    assert current["body"] == "internal-s07"
    assert "marcus.reid" in current["granted"]
    second = client.post(
        "/supplier-contracts/approvals",
        headers=claire,
        json={
            "draft_id": current["draft_id"],
            "version": current["version"],
            "content_sha256": current["content_sha256"],
            "approval_nonce": current["approval_nonce"],
        },
    )
    assert second.status_code == 200
    assert set(second.json()["granted"]) == {"marcus.reid", "claire.whitfield"}
    assert second.json()["state"] == "pending"
    sandra = _login(client, "sandra.executive@healthcore.example")
    sandra_view = client.get(f"/supplier-contracts/drafts/{draft['draft_id']}", headers=sandra)
    assert sandra_view.status_code == 200
    assert sandra_view.json()["draft_id"] == draft["draft_id"]
    third = client.post(
        "/supplier-contracts/approvals",
        headers=sandra,
        json={
            "draft_id": sandra_view.json()["draft_id"],
            "version": sandra_view.json()["version"],
            "content_sha256": sandra_view.json()["content_sha256"],
            "approval_nonce": sandra_view.json()["approval_nonce"],
        },
    )
    assert third.status_code == 200
    assert set(third.json()["granted"]) == {"marcus.reid", "claire.whitfield", "sandra.okonkwo"}
    assert third.json()["state"] == "approved"
