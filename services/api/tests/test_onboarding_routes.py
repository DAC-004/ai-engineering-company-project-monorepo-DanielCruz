"""People/hire views and authorization. Uses disposable identity and onboarding stores."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from agents.onboarding_orchestrator.seed import FIXTURE_PASSWORD, FIXTURE_USERS, onboarding_specs
from app.schemas.user import UserCreate, UserRole
from app.services import profile_service, user_service
from app.services.onboarding_service import reset_onboarding_runtime
from app.services.platform_access_seed import ensure_roles_and_departments

PEOPLE_EMAIL = "people.ops@onboarding.example"
HIRE_AUSTIN_EMAIL = "hire.austin@onboarding.example"
HIRE_LONDON_EMAIL = "hire.london@onboarding.example"
MANAGER_REVENUE_EMAIL = "manager.revenue@onboarding.example"


@pytest.fixture
def onboarding_client(tmp_path, monkeypatch, isolated_identity_store, client: TestClient):
    monkeypatch.setenv("ONBOARDING_CHECKPOINT_PATH", str(tmp_path / "onb.sqlite"))
    monkeypatch.setenv("ONBOARDING_STORE_PATH", str(tmp_path / "onb-store.json"))
    monkeypatch.setenv("ONBOARDING_AUDIT_PATH", str(tmp_path / "onb-audit.jsonl"))
    monkeypatch.setenv("ONBOARDING_START_DATE_COUNTS_AS_DAY", "1")
    monkeypatch.setenv("ONBOARDING_TIMEZONE", "UTC")
    monkeypatch.setenv("ONBOARDING_HOLIDAYS", "")
    monkeypatch.delenv("ONBOARDING_CUTOFF_HOUR", raising=False)
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "1")
    reset_onboarding_runtime()
    ensure_roles_and_departments()
    users = {}
    for spec in FIXTURE_USERS:
        user = user_service.create_user(
            UserCreate(email=spec["email"], password=FIXTURE_PASSWORD, name=spec["name"]),
            role=UserRole(spec["role"]),
            department_id=spec["department_id"],
        )
        profile_service.create_profile(user_id=user.id, name=spec["name"])
        users[spec["key"]] = user
    return client, users


def _headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": FIXTURE_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _refresh(client: TestClient, onboarding_id: str, headers: dict[str, str]) -> dict:
    got = client.get(f"/onboarding/{onboarding_id}", headers=headers)
    assert got.status_code == 200, got.text
    return got.json()


def _start_austin(client: TestClient, users) -> dict:
    people = _headers(client, PEOPLE_EMAIL)
    spec = onboarding_specs({key: user.id for key, user in users.items()}, date(2026, 11, 9))[0]
    response = client.post("/onboarding", json=spec, headers=people)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["accepted"] is True
    assert "task_id" in body
    assert "onboarding" not in body
    job = client.get(f"/onboarding/jobs/{body['task_id']}", headers=people)
    assert job.status_code == 200, job.text
    job_body = job.json()
    assert job_body["task_id"] == body["task_id"]
    assert job_body["ready"] is True
    return _refresh(client, body["onboarding_id"], people)


def test_people_lists_active_onboardings_hire_sees_only_own(onboarding_client) -> None:
    client, users = onboarding_client
    created = _start_austin(client, users)
    people = _headers(client, PEOPLE_EMAIL)
    listed = client.get("/onboarding", headers=people)
    assert listed.status_code == 200
    assert listed.json()[0]["onboarding_id"] == created["onboarding_id"]
    hire = _headers(client, HIRE_AUSTIN_EMAIL)
    mine = client.get("/onboarding/me", headers=hire)
    assert mine.status_code == 200
    assert mine.json()["hire_user_id"] == users["hire_austin"].id
    london_hire = _headers(client, HIRE_LONDON_EMAIL)
    denied = client.get(f"/onboarding/{created['onboarding_id']}", headers=london_hire)
    assert denied.status_code == 403
    other_list = client.get("/onboarding", headers=london_hire)
    assert other_list.status_code == 200
    assert other_list.json() == []


def test_unrelated_department_cannot_approve_and_actions_are_automated(onboarding_client) -> None:
    client, users = onboarding_client
    created = _start_austin(client, users)
    people = _headers(client, PEOPLE_EMAIL)
    receipt = client.post(
        f"/onboarding/{created['onboarding_id']}/paperwork",
        json={
            "documents_received": True,
            "background_check_completed": True,
            "decision_nonce": created["decision_nonce"],
        },
        headers=people,
    )
    assert receipt.status_code == 202
    assert receipt.json()["actor_type"] == "automated_process"
    assert "onboarding" not in receipt.json()
    refreshed = _refresh(client, created["onboarding_id"], people)
    assert refreshed["pending_kind"] == "check"
    manager = _headers(client, MANAGER_REVENUE_EMAIL)
    forbidden = client.post(
        f"/onboarding/{created['onboarding_id']}/decision",
        json={"decision": "approve", "comment": "", "decision_nonce": refreshed["decision_nonce"]},
        headers=manager,
    )
    assert forbidden.status_code in {403, 409}
    early = _headers(client, HIRE_AUSTIN_EMAIL)
    blocked = client.post(
        f"/onboarding/{created['onboarding_id']}/access-requests",
        json={"system_id": "us_ehr"},
        headers=early,
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "patient_system_before_compliance_approval"


def test_duplicate_start_and_invalid_office_framework_are_rejected_or_idempotent(onboarding_client) -> None:
    client, users = onboarding_client
    people = _headers(client, PEOPLE_EMAIL)
    spec = onboarding_specs({key: user.id for key, user in users.items()}, date(2026, 11, 9))[0]
    first = client.post("/onboarding", json=spec, headers=people)
    second = client.post("/onboarding", json=spec, headers=people)
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["onboarding_id"] == second.json()["onboarding_id"]
    listed = client.get("/onboarding", headers=people)
    matching = [row for row in listed.json() if row["onboarding_id"] == spec["onboarding_id"]]
    assert len(matching) == 1
    bad = dict(spec)
    bad["onboarding_id"] = "onb-mismatch"
    bad["framework"] = "uk_gdpr"
    rejected = client.post("/onboarding", json=bad, headers=people)
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "framework_office_mismatch"


def test_unlabeled_ni_and_bank_questions_are_rejected_without_echo(onboarding_client) -> None:
    client, users = onboarding_client
    created = _start_austin(client, users)
    hire = _headers(client, HIRE_AUSTIN_EMAIL)
    ni = "QQ123456C"
    iban = "GB82WEST12345698765432"
    ni_response = client.post(
        f"/onboarding/{created['onboarding_id']}/questions",
        json={"question": f"Please store {ni}"},
        headers=hire,
    )
    assert ni_response.status_code == 400
    assert ni_response.json()["detail"] == "sensitive_data_excluded"
    assert ni not in ni_response.text
    iban_response = client.post(
        f"/onboarding/{created['onboarding_id']}/questions",
        json={"question": f"Payroll {iban}"},
        headers=hire,
    )
    assert iban_response.status_code == 400
    assert iban_response.json()["detail"] == "sensitive_data_excluded"
    assert iban not in iban_response.text
    assert created["decision_nonce"]
    assert len(created["decision_nonce"]) == 32


def test_unlabeled_fictional_identifiers_never_reach_response_or_stores(onboarding_client) -> None:
    from app.services.onboarding_service import get_runtime

    client, users = onboarding_client
    created = _start_austin(client, users)
    hire = _headers(client, HIRE_AUSTIN_EMAIL)
    runtime = get_runtime()
    stores_before = {path: path.read_bytes() for path in [runtime.paths.checkpoint, runtime.paths.store, runtime.paths.audit, runtime.paths.outbox] if path.exists()}
    for sentinel in ["ZZ0000000", "00000000", "000000000"]:
        response = client.post(
            f"/onboarding/{created['onboarding_id']}/questions",
            json={"question": f"Do not retain this fictional identifier {sentinel}"},
            headers=hire,
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "sensitive_data_excluded"
        assert sentinel not in response.text
        for path, original in stores_before.items():
            assert path.read_bytes() == original
