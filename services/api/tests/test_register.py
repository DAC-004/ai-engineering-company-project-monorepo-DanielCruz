"""POST /users — Admin-only user administration."""

from __future__ import annotations

import threading

from fastapi import HTTPException

from app.core.security import verify_password
from app.db.tinydb import profiles_table
from app.schemas.access_admin import UserAdminCreate
from app.schemas.user import UserCreate, UserRole
from app.services import profile_service, user_service
from conftest import TEST_EMAIL, TEST_PASSWORD


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_unauthenticated_post_users_is_unauthorized(client) -> None:
    response = client.post(
        "/users",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "name": "Alice"},
    )
    assert response.status_code == 401


def test_employee_post_users_is_forbidden(client, seeded_user) -> None:
    headers = _login(client, TEST_EMAIL, TEST_PASSWORD)
    response = client.post(
        "/users",
        json={"email": "new.employee@healthcore.example", "password": TEST_PASSWORD},
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role permissions"
    assert user_service.get_user_by_email("new.employee@healthcore.example") is None


def test_supervisor_post_users_is_forbidden(client) -> None:
    user_service.create_user(
        UserCreate(email="marcus.creator@healthcore.example", password=TEST_PASSWORD),
        role=UserRole.supervisor,
        department_id="clinical_operations",
    )
    headers = _login(client, "marcus.creator@healthcore.example", TEST_PASSWORD)
    response = client.post(
        "/users",
        json={"email": "new.supervisor.create@healthcore.example", "password": TEST_PASSWORD},
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role permissions"
    assert user_service.get_user_by_email("new.supervisor.create@healthcore.example") is None


def test_admin_creates_hashed_user_and_profile(client) -> None:
    admin = user_service.create_user(
        UserCreate(email="admin.creator@healthcore.example", password=TEST_PASSWORD),
        role=UserRole.admin,
        department_id="technology",
    )
    headers = _login(client, admin.email, TEST_PASSWORD)
    response = client.post(
        "/users",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Alice",
            "phone": "+15125550100",
            "address": "Austin TX",
            "role_id": "employee",
            "department_id": "patient_experience",
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == TEST_EMAIL
    assert body["role"] == "employee"
    assert body["role_id"] == "employee"
    assert body["department_id"] == "patient_experience"
    assert "password" not in body
    assert "hashed_password" not in body

    stored = user_service.get_user_by_email(TEST_EMAIL)
    assert stored is not None
    assert stored.hashed_password != TEST_PASSWORD
    assert verify_password(TEST_PASSWORD, stored.hashed_password)
    matching = [user for user in user_service.list_users() if user.email == TEST_EMAIL]
    assert len(matching) == 1

    profile = profile_service.get_profile_by_user_id(stored.id)
    assert profile is not None
    assert profile.user_id == stored.id
    assert profile.name == "Alice"
    assert len([row for row in profiles_table().all() if row.get("user_id") == stored.id]) == 1


def test_admin_create_stores_mixed_case_email_in_lowercase(client) -> None:
    admin = user_service.create_user(
        UserCreate(email="admin.case@healthcore.example", password=TEST_PASSWORD),
        role=UserRole.admin,
        department_id="technology",
    )
    headers = _login(client, admin.email, TEST_PASSWORD)
    response = client.post(
        "/users",
        json={"email": "Alice@HealthCore.com", "password": TEST_PASSWORD},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    stored = user_service.get_user_by_email("alice@healthcore.com")
    assert stored is not None
    assert stored.email == "alice@healthcore.com"


def test_admin_create_rejects_duplicate_email(client) -> None:
    admin = user_service.create_user(
        UserCreate(email="admin.dup@healthcore.example", password=TEST_PASSWORD),
        role=UserRole.admin,
        department_id="technology",
    )
    headers = _login(client, admin.email, TEST_PASSWORD)
    payload = {"email": TEST_EMAIL, "password": TEST_PASSWORD, "name": "Alice"}
    first = client.post("/users", json=payload, headers=headers)
    assert first.status_code == 201, first.text

    duplicate = client.post(
        "/users",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "name": "Duplicate"},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "A user with this email already exists."
    users = [user for user in user_service.list_users() if user.email == TEST_EMAIL]
    assert len(users) == 1
    assert profile_service.get_profile_by_user_id(users[0].id) is not None
    assert (
        len([row for row in profiles_table().all() if row.get("user_id") == users[0].id])
        == 1
    )


def test_admin_create_concurrent_canonical_email_persists_one_identity(monkeypatch) -> None:
    admin = user_service.create_user(
        UserCreate(email="admin.concurrent@healthcore.example", password=TEST_PASSWORD),
        role=UserRole.admin,
        department_id="technology",
    )
    original_create = user_service.create_user
    barrier = threading.Barrier(2)
    created: list[object] = []
    conflicts: list[int] = []
    unexpected: list[BaseException] = []

    def overlapping_create(*args, **kwargs):
        barrier.wait(timeout=5)
        return original_create(*args, **kwargs)

    monkeypatch.setattr(user_service, "create_user", overlapping_create)

    payload = UserAdminCreate(
        email="Concurrent.User@HealthCore.example",
        password=TEST_PASSWORD,
        name="Concurrent",
        role_id=UserRole.employee,
        department_id="clinical_operations",
    )

    def invoke_handler() -> None:
        try:
            from app.routers import users as users_router

            created.append(
                users_router.create_user(payload=payload, _current_user=admin)
            )
        except HTTPException as exc:
            if exc.status_code == 409:
                conflicts.append(exc.status_code)
                if exc.detail != "A user with this email already exists.":
                    unexpected.append(exc)
            else:
                unexpected.append(exc)
        except BaseException as exc:
            unexpected.append(exc)

    threads = [threading.Thread(target=invoke_handler) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()

    assert unexpected == []
    assert len(created) == 1
    assert conflicts == [409]
    canonical = "concurrent.user@healthcore.example"
    users = [user for user in user_service.list_users() if user.email == canonical]
    assert len(users) == 1
    assert users[0].role == UserRole.employee
    assert users[0].role_id == UserRole.employee
    assert users[0].department_id == "clinical_operations"
    assert users[0].hashed_password != TEST_PASSWORD
    assert verify_password(TEST_PASSWORD, users[0].hashed_password)
    assert created[0].email == canonical
    assert created[0].id == users[0].id
    profiles = [row for row in profiles_table().all() if row.get("user_id") == users[0].id]
    assert len(profiles) == 1
    assert profile_service.get_profile_by_user_id(users[0].id) is not None
