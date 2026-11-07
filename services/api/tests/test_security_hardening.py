"""Reproducible real auth weaknesses; synthetic users and no provider calls."""

from __future__ import annotations
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.core.config import get_settings
from app.db.tinydb import reset_db_for_tests


@pytest.fixture
def security_client(tmp_path, monkeypatch):
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "auth.json"))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + (tmp_path / "inventory.db").as_posix())
    monkeypatch.setenv("SECRET_KEY", "fictional-security-test-only-secret")
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "1")
    get_settings.cache_clear()
    reset_db_for_tests()
    from app.main import app

    with TestClient(app) as client:
        yield client
    reset_db_for_tests()
    get_settings.cache_clear()


def test_login_brute_force_gets_explicit_429(security_client):
    statuses = [
        security_client.post(
            "/auth/login", data={"username": "unknown@example.invalid", "password": "wrong"}
        )
        for _ in range(12)
    ]
    assert any(response.status_code == 429 for response in statuses)
    rejected = next(response for response in statuses if response.status_code == 429)
    assert int(rejected.headers["Retry-After"]) > 0


def test_unknown_account_does_not_skip_password_verification(security_client, monkeypatch):
    from app.routers import auth

    calls = []
    monkeypatch.setattr(auth.user_service, "get_user_by_email", lambda _email: None)
    monkeypatch.setattr(
        auth, "verify_password", lambda password, hashed: calls.append(hashed) or False
    )
    response = security_client.post("/auth/login", data={"username": "not-registered@security.example", "password": "wrong"})
    assert response.status_code == 401
    assert len(calls) == 1


def test_reset_token_cannot_be_reused_concurrently(security_client, monkeypatch):
    from app.schemas.user import UserCreate, UserRole
    from app.services import user_service, password_reset_service as reset

    user = user_service.create_user(
        UserCreate(email="reset-race@security.example", password="FictionalPassword1!"),
        role=UserRole.employee,
    )
    raw = reset.create_reset_token_for_user(user)
    original = reset._load_valid_token_row
    updates = []

    def slow_load(token):
        row = original(token)
        time.sleep(0.1)
        return row

    monkeypatch.setattr(reset, "_load_valid_token_row", slow_load)
    monkeypatch.setattr(
        reset.user_service, "update_user", lambda *args, **kwargs: updates.append(True) or user
    )
    start = threading.Barrier(2)

    def attempt(_):
        start.wait()
        try:
            reset.reset_password_with_token(token=raw, new_password="FictionalNewPassword2!")
            return "accepted"
        except reset.InvalidResetTokenError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    assert outcomes.count("accepted") == 1
    assert outcomes.count("rejected") == 1
    assert len(updates) == 1


def test_recovery_and_critical_write_limits_are_explicit(security_client, monkeypatch):
    from app.services import password_reset_service

    calls = []
    monkeypatch.setattr(
        password_reset_service, "request_password_reset", lambda _email: calls.append(True)
    )
    responses = [
        security_client.post("/auth/forgot-password", json={"email": "synthetic@security.example"})
        for _ in range(7)
    ]
    assert [response.status_code for response in responses] == [200] * 5 + [429] * 2
    assert len(calls) == 5
    writes = [security_client.post("/users", json={}) for _ in range(62)]
    assert writes[-1].status_code == 429
    assert writes[-1].headers["Retry-After"]


def test_atomic_rate_budget_and_window_expiry(security_client):
    from app.core.sensitive_rate_limit import take

    with ThreadPoolExecutor(max_workers=10) as pool:
        accepted = list(
            pool.map(lambda _: take("controlled-address", "test", 5, now=1000)[0], range(20))
        )
    assert sum(accepted) == 5
    assert take("controlled-address", "test", 5, now=1020)[0]


def test_jwt_rotation_accepts_overlap_and_rejects_retired_key(security_client, monkeypatch):
    from app.core.security import create_access_token, decode_access_token, JWTError

    old_key = "fictional-old-key-for-rotation-test-only"
    new_key = "fictional-new-key-for-rotation-test-only"
    monkeypatch.setenv("SECRET_KEY", old_key)
    get_settings.cache_clear()
    old_token = create_access_token(subject="opaque-subject")
    monkeypatch.setenv("SECRET_KEY", new_key)
    monkeypatch.setenv("JWT_PREVIOUS_SECRET_KEYS", old_key)
    get_settings.cache_clear()
    assert decode_access_token(old_token)["sub"] == "opaque-subject"
    new_token = create_access_token(subject="new-subject")
    assert decode_access_token(new_token)["sub"] == "new-subject"
    monkeypatch.setenv("JWT_PREVIOUS_SECRET_KEYS", "")
    get_settings.cache_clear()
    with pytest.raises(JWTError):
        decode_access_token(old_token)
    assert decode_access_token(new_token)["sub"] == "new-subject"
