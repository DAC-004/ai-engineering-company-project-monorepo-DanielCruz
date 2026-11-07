"""Real outbox/worker contract with a simulated external provider, never real email."""

from __future__ import annotations
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from app.core.config import get_settings
from app.db.tinydb import reset_db_for_tests


@pytest.fixture
def isolated_email(tmp_path, monkeypatch):
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.sqlite3"))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + (tmp_path / "inventory.db").as_posix())
    monkeypatch.delenv("RFP_DEMONSTRATION_PASSWORD", raising=False)
    monkeypatch.delenv("PLATFORM_SEED_PASSWORD", raising=False)
    from app.db.database import reset_engine_for_tests
    reset_engine_for_tests()
    monkeypatch.setenv("SECRET_KEY", "fictional-outbox-test-key-32-characters")
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "1")
    get_settings.cache_clear()
    reset_db_for_tests()
    from app.services import email_outbox

    yield email_outbox
    reset_engine_for_tests()
    get_settings.cache_clear()
    reset_db_for_tests()


def fixture_job(outbox):
    from app.services import user_service
    from app.schemas.user import UserCreate, UserRole
    from app.services.password_reset_service import create_reset_token_for_user, build_reset_url

    user = user_service.create_user(
        UserCreate(email="fictional@audit.example", password="FictionalPassword1!"),
        role=UserRole.employee,
    )
    raw = create_reset_token_for_user(user)
    job = outbox.create_job(user_id=user.id, to_email=user.email, reset_url=build_reset_url(raw))
    return job, raw


def test_queue_contract_contains_only_uuid_and_request_does_not_call_provider(
    isolated_email, monkeypatch
):
    from app.services import password_reset_service, user_service, email_service
    from app.email_tasks import deliver_reset_email

    job, raw = fixture_job(isolated_email)
    published = []
    monkeypatch.setattr(
        deliver_reset_email, "apply_async", lambda **kwargs: published.append(kwargs)
    )
    monkeypatch.setattr(
        email_service,
        "send_password_reset_email",
        lambda **kwargs: pytest.fail("request called provider"),
    )
    password_reset_service.request_password_reset("fictional@audit.example")
    assert len(published) == 1
    assert len(published[0]["args"]) == 1
    from uuid import UUID

    UUID(published[0]["args"][0])
    blob = isolated_email.outbox_path().read_bytes()
    assert raw.encode() not in blob and b"fictional@audit.example" not in blob


def test_duplicate_queue_delivery_has_one_effect_and_one_provider_key(isolated_email, monkeypatch):
    from app.email_tasks import deliver_reset_email
    from app.services import email_service

    job, raw = fixture_job(isolated_email)
    sent = []

    def provider(**kwargs):
        sent.append(kwargs["idempotency_key"])
        return "fake-provider-id"

    monkeypatch.setattr(email_service, "send_password_reset_email", provider)
    deliver_reset_email.run(job)
    deliver_reset_email.run(job)
    assert sent == ["healthcore-reset-" + job]
    assert isolated_email.public_status(job)["state"] == "completed"
    with isolated_email.connection() as db:
        assert (
            db.execute("SELECT ciphertext FROM email_jobs WHERE id=?", (job,)).fetchone()[0] is None
        )


def test_concurrent_worker_claims_have_single_owner(isolated_email):
    job, raw = fixture_job(isolated_email)
    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(lambda _: isolated_email.claim(job), range(4)))
    assert sum(value is not None for value in values) == 1


def test_exponential_retry_exhaustion_is_durable_and_queryable(isolated_email, monkeypatch):
    from app.email_tasks import deliver_reset_email
    from app.services import email_service

    job, raw = fixture_job(isolated_email)
    now = [1000.0]
    # Real job timestamps precede the first claim; advance beyond its creation.
    now[0] = isolated_email.public_status(job)["available"]
    monkeypatch.setattr(isolated_email.time, "time", lambda: now[0])
    delays = []

    def retry(**kwargs):
        delays.append(kwargs["countdown"])
        raise RuntimeError("scheduled retry")

    monkeypatch.setattr(deliver_reset_email, "retry", retry)

    def unavailable(**kwargs):
        raise email_service.EmailDeliveryError("provider unavailable")

    monkeypatch.setattr(email_service, "send_password_reset_email", unavailable)
    for attempt in range(3):
        if attempt < 2:
            with pytest.raises(RuntimeError, match="scheduled retry"):
                deliver_reset_email.run(job)
            now[0] += delays[-1]
        else:
            deliver_reset_email.run(job)
    status = isolated_email.public_status(job)
    assert delays == [2, 4]
    assert status["state"] == "failed" and status["attempts"] == 3
    assert isolated_email.dead_letters()[0]["id"] == job
    assert status["error_code"] == "provider_unavailable"


def test_broker_publish_failure_retains_pending_work(isolated_email, monkeypatch):
    from app.email_tasks import deliver_reset_email

    monkeypatch.setattr(
        deliver_reset_email,
        "apply_async",
        lambda **kwargs: (_ for _ in ()).throw(ConnectionError("private broker details")),
    )
    job = isolated_email.enqueue_reset_email(
        user_id=str(uuid4()),
        to_email="synthetic@example.invalid",
        reset_url="http://localhost/reset-password?token=synthetic",
    )
    assert job in isolated_email.pending_jobs()
    assert isolated_email.public_status(job)["state"] == "pending"


def test_sdk_adapter_preserves_idempotency_key_and_requires_ack(isolated_email, monkeypatch):
    from app.services import email_service

    monkeypatch.setenv("RESEND_API_KEY", "fictional-test-only-no-provider-contact")
    get_settings.cache_clear()
    calls = []
    monkeypatch.setattr(
        email_service.resend.Emails,
        "send",
        lambda params, options: calls.append(options) or {"id": "fake-provider-id"},
    )
    assert (
        email_service.send_password_reset_email(
            to_email="synthetic@async.example",
            reset_url="http://localhost/reset?token=synthetic",
            idempotency_key="same-operation",
        )
        == "fake-provider-id"
    )
    assert calls == [{"idempotency_key": "same-operation"}]
    monkeypatch.setattr(email_service.resend.Emails, "send", lambda *args, **kwargs: {})
    with pytest.raises(email_service.EmailDeliveryError):
        email_service.send_password_reset_email(
            to_email="synthetic@async.example",
            reset_url="http://localhost/reset?token=synthetic",
            idempotency_key="same-operation",
        )


def test_status_and_dead_letters_require_admin_and_exclude_payload(isolated_email):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services import user_service
    from app.schemas.user import UserCreate, UserRole
    from app.core.security import create_access_token
    job, raw=fixture_job(isolated_email)
    admin=user_service.create_user(UserCreate(email="admin@async.example", password="SyntheticPassword1!"), role=UserRole.admin)
    employee=user_service.get_user_by_email("fictional@audit.example")
    def headers(user): return {"Authorization":"Bearer "+create_access_token(subject=user.id)}
    with TestClient(app) as client:
        assert client.get("/tasks/email/"+job).status_code==401
        assert client.get("/tasks/email/"+job,headers=headers(employee)).status_code==403
        response=client.get("/tasks/email/"+job,headers=headers(admin))
        assert response.status_code==200 and response.json()["state"]=="pending"
        assert raw not in response.text and "ciphertext" not in response.text and "to_email" not in response.text
        assert client.get("/tasks/email/dead-letters",headers=headers(admin)).status_code==200
        assert client.get("/tasks/email/dead-letters",headers=headers(employee)).status_code==403


def test_invalidated_reset_is_not_sent(isolated_email, monkeypatch):
    from app.email_tasks import deliver_reset_email
    from app.services import email_service,password_reset_service,user_service
    job, raw=fixture_job(isolated_email)
    user=user_service.get_user_by_email("fictional@audit.example")
    password_reset_service.create_reset_token_for_user(user)
    monkeypatch.setattr(email_service,"send_password_reset_email",lambda **kwargs: pytest.fail("invalidated reset sent"))
    deliver_reset_email.run(job)
    assert isolated_email.public_status(job)["error_code"]=="reset_invalidated"
    assert isolated_email.public_status(job)["state"]=="failed"


def test_reset_delivery_has_distinct_process_audit_identity(isolated_email, monkeypatch):
    from app.email_tasks import deliver_reset_email
    from app.services import email_service
    from app.audit.capture import configured_store
    job, _raw = fixture_job(isolated_email)
    monkeypatch.setattr(email_service, "send_password_reset_email", lambda **_kwargs: "fictional-provider-id")
    deliver_reset_email.run(job)
    assert isolated_email.public_status(job)["state"] == "completed"
    rows = configured_store().query(action="task.execute", limit=100)["items"]
    assert {r["outcome"] for r in rows if r["actor_ref"] == "process:password-reset-email"} == {"attempted", "success"}


def test_pending_delivery_survives_configured_key_rotation_overlap(isolated_email, monkeypatch):
    from app.email_tasks import deliver_reset_email
    from app.services import email_service
    old_key = get_settings().secret_key
    job, _raw = fixture_job(isolated_email)
    sent = []
    monkeypatch.setattr(email_service, "send_password_reset_email", lambda **_kwargs: sent.append(True) or "fictional-provider-id")
    monkeypatch.setenv("SECRET_KEY", "fictional-new-active-outbox-key-only")
    monkeypatch.setenv("JWT_PREVIOUS_SECRET_KEYS", old_key)
    get_settings.cache_clear()
    deliver_reset_email.run(job)
    assert sent == [True]
    assert isolated_email.public_status(job)["state"] == "completed"
    # New payloads must use the active key, not a retired verification key.
    from app.services import user_service, password_reset_service
    user = user_service.get_user_by_email("fictional@audit.example")
    raw = password_reset_service.create_reset_token_for_user(user)
    new_job = isolated_email.create_job(user_id=user.id, to_email=user.email, reset_url=password_reset_service.build_reset_url(raw))
    monkeypatch.setenv("JWT_PREVIOUS_SECRET_KEYS", "")
    get_settings.cache_clear()
    deliver_reset_email.run(new_job)
    assert sent == [True, True]
    assert isolated_email.public_status(new_job)["state"] == "completed"



def test_retired_key_without_overlap_does_not_decrypt_pending_delivery(isolated_email, monkeypatch):
    from app.email_tasks import deliver_reset_email
    from app.services import email_service
    job, _raw = fixture_job(isolated_email)
    monkeypatch.setattr(email_service, "send_password_reset_email", lambda **_kwargs: pytest.fail("retired key delivered a message"))
    monkeypatch.setenv("SECRET_KEY", "fictional-new-active-outbox-key-only")
    monkeypatch.setenv("JWT_PREVIOUS_SECRET_KEYS", "")
    get_settings.cache_clear()
    deliver_reset_email.run(job)
    assert isolated_email.public_status(job)["state"] == "failed"
