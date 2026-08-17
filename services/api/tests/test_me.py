"""GET /auth/me — current-user resolution after token validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jose import jwt

from app.core.config import get_settings
from app.core.security import create_access_token
from app.services import user_service
from tests.conftest import TEST_EMAIL, TEST_PASSWORD


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login_token(client) -> str:
    response = client.post(
        "/auth/login",
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_me_returns_email_role_and_profile_for_valid_token(client, seeded_user) -> None:
    token = _login_token(client)
    response = client.get("/auth/me", headers=_bearer(token))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == TEST_EMAIL
    assert body["role"] == "user"
    assert body["profile"] is not None
    assert body["profile"]["name"] == "Alice"
    assert body["profile"]["user_id"] == seeded_user.id


def test_me_rejects_token_for_deleted_user(client, seeded_user) -> None:
    token = create_access_token(subject=seeded_user.id)
    user_service.delete_user(seeded_user.id)

    response = client.get("/auth/me", headers=_bearer(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_me_rejects_token_without_sub(client, seeded_user) -> None:
    settings = get_settings()
    token = jwt.encode(
        {"exp": datetime.now(UTC) + timedelta(minutes=30)},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get("/auth/me", headers=_bearer(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_me_rejects_expired_token(client, seeded_user) -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": seeded_user.id,
            "exp": datetime.now(UTC) - timedelta(minutes=5),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get("/auth/me", headers=_bearer(token))

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_me_rejects_malformed_token(client, seeded_user) -> None:
    response = client.get("/auth/me", headers=_bearer("not-a-jwt"))

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"
