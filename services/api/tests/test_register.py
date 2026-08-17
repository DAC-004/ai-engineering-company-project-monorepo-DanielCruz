"""POST /users — registration application logic."""

from __future__ import annotations

from app.core.security import verify_password
from app.services import profile_service, user_service
from tests.conftest import TEST_EMAIL, TEST_PASSWORD


def test_register_creates_hashed_user_with_default_role_and_profile(client) -> None:
    response = client.post(
        "/users",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Alice",
            "phone": "+15125550100",
            "address": "Austin TX",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == TEST_EMAIL
    assert body["role"] == "user"
    assert "password" not in body
    assert "hashed_password" not in body

    stored = user_service.get_user_by_email(TEST_EMAIL)
    assert stored is not None
    # Password must be persisted as a bcrypt hash, not plaintext.
    assert stored.hashed_password != TEST_PASSWORD
    assert verify_password(TEST_PASSWORD, stored.hashed_password)

    profile = profile_service.get_profile_by_user_id(stored.id)
    assert profile is not None
    assert profile.user_id == stored.id
    assert profile.name == "Alice"


def test_register_stores_mixed_case_email_in_lowercase(client) -> None:
    response = client.post(
        "/users",
        json={"email": "Alice@HealthCore.com", "password": TEST_PASSWORD},
    )

    assert response.status_code == 201
    stored = user_service.get_user_by_email("alice@healthcore.com")
    assert stored is not None
    assert stored.email == "alice@healthcore.com"


def test_register_rejects_duplicate_email(client) -> None:
    payload = {"email": TEST_EMAIL, "password": TEST_PASSWORD, "name": "Alice"}
    first = client.post("/users", json=payload)
    assert first.status_code == 201

    duplicate = client.post(
        "/users",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "name": "Duplicate"},
    )

    assert duplicate.status_code == 409
    users = [user for user in user_service.list_users() if user.email == TEST_EMAIL]
    assert len(users) == 1
