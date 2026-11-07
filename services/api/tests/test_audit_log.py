"""Audit accountability/privacy boundaries, actual capture and tamper evidence."""

import json, os, sqlite3, subprocess, sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from shared.healthcore_audit.store import (
    AuditStore,
    AuditIntegrityError,
    event,
    record_patient_event,
)
from shared.healthcore_audit.seed import seed_synthetic


def sample(**changes):
    data = event(
        actor_kind="human",
        actor_ref=str(uuid4()),
        action="patient.read",
        resource_kind="clinical_record",
        resource_ref=str(uuid4()),
        patient_ref=str(uuid4()),
        department_id="clinical_operations",
        origin="192.0.2.1",
        context="routine_review",
        outcome="success",
    )
    data.update(changes)
    return data


def test_immutable_rows_and_tamper_detection(tmp_path):
    store = AuditStore(tmp_path / "audit.db")
    seed_synthetic(store)
    with sqlite3.connect(store.path) as c:
        for sql in [
            "UPDATE audit_entries SET payload='{}' WHERE seq=1",
            "DELETE FROM audit_entries WHERE seq=1",
        ]:
            with pytest.raises(sqlite3.IntegrityError):
                c.execute(sql)
    assert store.verify() == {"valid": True, "checked": 18}
    # Simulate offline filesystem/DB-admin tampering, beyond the application.
    with sqlite3.connect(store.path) as c:
        c.execute("DROP TRIGGER audit_no_update")
        original = json.loads(
            c.execute("SELECT payload FROM audit_entries WHERE seq=1").fetchone()[0]
        )
        original["outcome"] = "denied"
        c.execute("UPDATE audit_entries SET payload=? WHERE seq=1", (json.dumps(original),))
    assert store.verify()["valid"] is False
    with pytest.raises(AuditIntegrityError):
        store.query(limit=100)


def test_truncated_tail_is_detected_against_head(tmp_path):
    store = AuditStore(tmp_path / "audit.db")
    seed_synthetic(store)
    with sqlite3.connect(store.path) as c:
        c.execute("DROP TRIGGER audit_no_delete")
        c.execute("DELETE FROM audit_entries WHERE seq=18")
    assert store.verify()["valid"] is False
    with pytest.raises(AuditIntegrityError):
        store.append(sample())


@pytest.mark.parametrize(
    "changes",
    [
        {"patient_name": "Do Not Store"},
        {"context": "Diagnosis: private text"},
        {"patient_ref": "Alice Smith"},
        {"actor_ref": "person@example.com"},
        {"origin": "https://private.example/clinical"},
        {"action": "diagnosis_private_text"},
        {"resource_ref": "Patient Alice Smith"},
    ],
)
def test_ledger_rejects_phi_free_text_and_unknown_fields(tmp_path, changes):
    store = AuditStore(tmp_path / "audit.db")
    with pytest.raises((ValueError, TypeError)):
        store.append(sample(**changes))
    assert not store.path.exists()


def test_synthetic_seed_is_complete_and_idempotent(tmp_path):
    store = AuditStore(tmp_path / "audit.db")
    assert seed_synthetic(store) == 18
    assert seed_synthetic(store) == 0
    rows = store.query(limit=100)["items"]
    assert len(rows) == 18 and len({r["patient_ref"] for r in rows}) == 18
    assert {
        "patient.read",
        "patient.update",
        "patient.export",
        "billing.update",
        "claim.approve",
        "claim.deny",
        "agent.patient_access",
    } <= {r["action"] for r in rows}
    assert any(r["actor_kind"] == "process" and r["initiator_ref"] for r in rows)


def test_patient_boundary_requires_opaque_reference(tmp_path):
    store = AuditStore(tmp_path / "audit.db")
    row = record_patient_event(
        store=store,
        patient_ref=str(uuid4()),
        department_id="clinical_operations",
        actor_kind="human",
        actor_ref=str(uuid4()),
        action="patient.read",
        context="referral_resolution",
        origin="192.0.2.5",
    )
    assert row["context"] == "referral_resolution"
    with pytest.raises(ValueError):
        record_patient_event(
            store=store,
            patient_ref="Jane Smith",
            department_id="clinical_operations",
            actor_kind="human",
            actor_ref=str(uuid4()),
            action="patient.read",
            context="routine_review",
            origin="192.0.2.5",
        )


def test_multiprocess_chain_has_no_lost_or_forked_entries(tmp_path):
    store = AuditStore(tmp_path / "audit.db")
    store.append(sample())
    script = "from shared.healthcore_audit.store import AuditStore,event;from uuid import uuid4;import sys;s=AuditStore(sys.argv[1]);[s.append(event(actor_kind='process',actor_ref='process:synthetic-seed',action='task.execute',resource_kind='task',resource_ref=str(uuid4()),department_id='technology',origin='process:synthetic-seed',context='automated_processing',outcome='success')) for _ in range(10)]"
    children = [
        subprocess.Popen(
            [sys.executable, "-B", "-c", script, str(store.path)],
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(4)
    ]
    for child in children:
        out, err = child.communicate(timeout=40)
        assert child.returncode == 0, err.decode()
    assert store.verify() == {"valid": True, "checked": 41}


def test_filters_and_pagination_do_not_overlap(tmp_path):
    store = AuditStore(tmp_path / "audit.db")
    seed_synthetic(store)
    first = store.query(action="patient.read", limit=3)
    second = store.query(action="patient.read", limit=3, offset=3)
    assert first["total"] == 8 and first["has_more"]
    assert not {r["seq"] for r in first["items"]} & {r["seq"] for r in second["items"]}
    row = first["items"][0]
    assert (
        store.query(
            actor_ref=row["actor_ref"],
            resource_ref=row["resource_ref"],
            start=row["occurred_at"],
            end=row["occurred_at"],
        )["total"]
        == 1
    )
    with pytest.raises(ValueError):
        store.query(start="2026-01-01T00:00:00")


@pytest.fixture
def audit_client(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.db.tinydb import reset_db_for_tests
    from app.db.database import reset_engine_for_tests
    from app.database import close_db

    for key, value in {
        "TINYDB_PATH": str(tmp_path / "auth.json"),
        "AUDIT_DB_PATH": str(tmp_path / "audit.db"),
        "DATABASE_URL": "sqlite:///" + (tmp_path / "inventory.db").as_posix(),
        "SUPPLIERS_DB_PATH": str(tmp_path / "suppliers.json"),
        "SECRET_KEY": "audit-fixture-secret-32-characters",
        "PLATFORM_SEED_PASSWORD": "",
        "RFP_DEMONSTRATION_PASSWORD": "",
        "CELERY_TASK_ALWAYS_EAGER": "1",
        "RESEND_API_KEY": "test-only-not-real",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    reset_db_for_tests()
    reset_engine_for_tests()
    close_db()
    from app.main import app
    from app.services import user_service
    from app.schemas.user import UserCreate, UserRole

    users = {}
    for role, dept in [
        ("admin", "technology"),
        ("supervisor", "clinical_operations"),
        ("employee", "clinical_operations"),
    ]:
        users[role] = user_service.create_user(
            UserCreate(email=role + "@audit.example", password="FixturePassword1!"),
            role=UserRole(role),
            department_id=dept,
        )
    with TestClient(app) as client:
        headers = {}
        for role in users:
            response = client.post(
                "/auth/login", data={"username": users[role].email, "password": "FixturePassword1!"}
            )
            assert response.status_code == 200, response.text
            headers[role] = {"Authorization": "Bearer " + response.json()["access_token"]}
        yield client, headers, users, AuditStore(tmp_path / "audit.db")
    get_settings.cache_clear()
    reset_db_for_tests()
    reset_engine_for_tests()
    close_db()


def test_viewer_roles_scope_filters_and_no_mutation_endpoint(audit_client):
    client, headers, users, store = audit_client
    seed_synthetic(store)
    assert client.get("/audit-log").status_code == 401
    assert client.get("/audit-log", headers=headers["employee"]).status_code == 403
    admin = client.get(
        "/audit-log", headers=headers["admin"], params={"action": "patient.read", "limit": 3}
    ).json()
    assert admin["total"] == 8 and len(admin["items"]) == 3
    scoped = client.get(
        "/audit-log",
        headers=headers["supervisor"],
        params={"limit": 100, "department_id": "revenue_cycle"},
    ).json()
    assert scoped["items"] and all(
        r["department_id"] == "clinical_operations" for r in scoped["items"]
    )
    assert client.get("/audit-log/integrity", headers=headers["supervisor"]).status_code == 403
    assert client.get("/audit-log/integrity", headers=headers["admin"]).json()["valid"]
    for method in ["post", "put", "patch", "delete"]:
        assert getattr(client, method)("/audit-log", headers=headers["admin"]).status_code == 405
    for query in [
        {"limit": 101},
        {"offset": -1},
        {"actor_ref": "Alice Smith"},
        {"resource_ref": "secret diagnosis"},
        {"action": "secret diagnosis"},
        {"start": "2026-01-01T00:00:00"},
    ]:
        assert client.get("/audit-log", headers=headers["admin"], params=query).status_code == 422
    assert "secret diagnosis" not in store.path.read_bytes().decode("latin1")


def test_actual_auth_and_user_assignment_capture_is_sanitized(audit_client):
    client, headers, users, store = audit_client
    bad = client.post(
        "/auth/login",
        data={"username": users["employee"].email, "password": "NeverLogThisPassword"},
    )
    assert bad.status_code == 401
    changed = client.patch(
        "/users/" + users["employee"].id + "/assignment",
        headers=headers["admin"],
        json={"role_id": "supervisor", "department_id": "revenue_cycle"},
    )
    assert changed.status_code == 200
    rows = store.query(limit=100)["items"]
    assert any(r["action"] == "auth.login" and r["outcome"] == "denied" for r in rows)
    assert any(
        r["action"] == "auth.login" and r["actor_kind"] == "human" and r["outcome"] == "success"
        for r in rows
    )
    assignment = [r for r in rows if r["action"] == "user.assignment" and r["outcome"] == "success"]
    assert {"clinical_operations", "revenue_cycle"} <= {r["department_id"] for r in assignment}
    assert all(r["actor_ref"] == users["admin"].id for r in assignment)
    raw = store.path.read_bytes()
    for private in [
        "NeverLogThisPassword",
        "FixturePassword1!",
        "employee@audit.example",
        "hashed_password",
        "access_token",
    ]:
        assert private.encode() not in raw


def test_real_process_wrapper_has_actor_but_never_payload(audit_client):
    from app.audit.process import audited_process

    client, headers, users, store = audit_client

    @audited_process("process:incident-analysis", "technology")
    def worker(secret):
        return {"patient_name": secret}

    assert worker("DoNotCopyThisName") == {"patient_name": "DoNotCopyThisName"}
    rows = store.query(action="task.execute")["items"]
    assert {r["outcome"] for r in rows} == {"attempted", "success"}
    assert all(
        r["actor_kind"] == "process" and r["actor_ref"] == "process:incident-analysis" for r in rows
    )
    assert b"DoNotCopyThisName" not in store.path.read_bytes()


def test_unavailable_ledger_stops_request_before_mutation(audit_client, monkeypatch):
    from shared.healthcore_audit.store import AuditError
    from app.services import user_service

    client, headers, users, store = audit_client

    def unavailable(*args, **kwargs):
        raise AuditError("unavailable")

    monkeypatch.setattr(AuditStore, "append", unavailable)
    response = client.post(
        "/users",
        headers=headers["admin"],
        json={"email": "must-not-exist@audit.example", "password": "FixturePassword1!"},
    )
    assert response.status_code == 503
    assert user_service.get_user_by_email("must-not-exist@audit.example") is None


def test_actual_incident_task_entry_point_is_audited_without_result_text(audit_client, monkeypatch):
    from app import tasks

    client, headers, users, store = audit_client
    cached = {"patient_name": "NeverCopyWorkerResult", "cache_hit": True}
    monkeypatch.setattr(tasks, "load_task_result", lambda _task_id: cached)
    tasks.analyze_incidents_task.push_request(id=str(uuid4()), retries=0)
    try:
        result = tasks.analyze_incidents_task.run("opaque-upload-id")
    finally:
        tasks.analyze_incidents_task.pop_request()
    assert result == cached
    rows = store.query(action="task.execute")["items"]
    assert {row["outcome"] for row in rows} == {"attempted", "success"}
    assert all(
        row["actor_kind"] == "process" and row["actor_ref"] == "process:incident-analysis"
        for row in rows
    )
    assert b"NeverCopyWorkerResult" not in store.path.read_bytes()


def test_direct_deactivation_has_opaque_target_and_process_attribution(audit_client):
    from app.services import user_service
    from app.schemas.user import UserUpdate

    client, headers, users, store = audit_client
    changed = user_service.update_user(users["employee"].id, UserUpdate(is_active=False))
    assert changed.is_active is False
    rows = store.query(resource_ref=users["employee"].id, action="user.update")["items"]
    assert any(row["outcome"] == "success" and row["actor_kind"] == "process" for row in rows)
    assert b"employee@audit.example" not in store.path.read_bytes()


def test_reporting_route_is_in_sensitive_inventory():
    from app.audit.middleware import classification

    assert classification("/reporting/pipeline-runs/latest", "GET") == (
        "report",
        "report.read",
        "routine_review",
    )


def test_chat_background_entry_point_has_process_capture(audit_client):
    from app.services.chat_channel import _generate_turn

    client, headers, users, store = audit_client
    _generate_turn("not-an-existing-session", "NeverLogThisChatQuestion")
    rows = store.query(action="task.execute")["items"]
    assert {row["outcome"] for row in rows} == {"attempted", "success"}
    assert all(row["actor_ref"] == "process:support-agent" for row in rows)
    assert b"NeverLogThisChatQuestion" not in store.path.read_bytes()
