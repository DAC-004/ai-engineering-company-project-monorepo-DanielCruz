"""AUTH-03 password-reset storage and API behavior (Resend mocked)."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from tinydb import Query

from app.core.config import get_settings
from app.db.tinydb import password_reset_tokens_table, reset_db_for_tests
from app.schemas.user import UserCreate, UserRole
from app.services.password_reset_service import create_reset_token_for_user
from app.services import user_service


@pytest.fixture()
def isolated_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    auth_path = tmp_path / "auth.json"
    monkeypatch.setenv("SECRET_KEY", "pytest-secret-key-32-chars-long!!")
    monkeypatch.setenv("TINYDB_PATH", str(auth_path))
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite:///{(tmp_path / 'inventory.db').resolve().as_posix()}",
    )
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "HealthCore <onboarding@resend.dev>")
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://localhost:3000")
    monkeypatch.setenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "1")
    monkeypatch.delenv("PLATFORM_SEED_PASSWORD", raising=False)
    monkeypatch.delenv("RFP_DEMONSTRATION_PASSWORD", raising=False)
    get_settings.cache_clear()
    reset_db_for_tests()
    auth_path.write_text("{}", encoding="utf-8")
    from app.main import app

    with TestClient(app) as client:
        yield client
    reset_db_for_tests()
    get_settings.cache_clear()


def _register(_client: TestClient, email: str, password: str) -> None:
    user_service.create_user(UserCreate(email=email, password=password), role=UserRole.employee)


def test_reset_token_row_stores_hash_only(isolated_client: TestClient) -> None:
    email = "hash-only@example.com"
    _register(isolated_client, email, "password-one-1")
    user = user_service.get_user_by_email(email)
    assert user is not None

    raw = create_reset_token_for_user(user)
    table = password_reset_tokens_table()
    rows = table.all()
    assert len(rows) == 1
    row = rows[0]
    assert row["token_hash"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert raw not in str(row.values())


def test_forgot_password_mocks_resend(isolated_client: TestClient) -> None:
    email = "mock-send@example.com"
    _register(isolated_client, email, "password-one-1")
    with patch("app.services.email_service.send_password_reset_email") as send_email:
        response = isolated_client.post("/auth/forgot-password", json={"email": email})
    assert response.status_code == 200
    send_email.assert_called_once()
    assert send_email.call_args.kwargs["to_email"] == email
    assert "/reset-password?token=" in send_email.call_args.kwargs["reset_url"]


def test_expired_and_reused_tokens_rejected(isolated_client: TestClient) -> None:
    email = "reuse@example.com"
    password = "password-one-1"
    new_password = "password-two-2"
    _register(isolated_client, email, password)

    captured_url: list[str] = []

    def capture_send(*, to_email: str, reset_url: str) -> None:
        captured_url.append(reset_url)

    with patch("app.services.email_service.send_password_reset_email", side_effect=capture_send):
        assert isolated_client.post("/auth/forgot-password", json={"email": email}).status_code == 200

    assert captured_url
    token = captured_url[0].split("token=", 1)[1]

    reset_ok = isolated_client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": new_password},
    )
    assert reset_ok.status_code == 200, reset_ok.text

    reused = isolated_client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "password-three-3"},
    )
    assert reused.status_code == 400

    table = password_reset_tokens_table()
    Token = Query()
    row = table.get(Token.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest())
    assert row is not None
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    table.update({"expires_at": past}, doc_ids=[row.doc_id])

    expired = isolated_client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "password-four-4"},
    )
    assert expired.status_code == 400

    login = isolated_client.post(
        "/auth/login",
        data={"username": email, "password": new_password},
    )
    assert login.status_code == 200
