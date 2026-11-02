"""User service — TinyDB CRUD for authentication accounts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from tinydb import Query

from app.access.catalog import is_known_department, normalize_role
from app.core.security import hash_password
from app.db.tinydb import identity_mutation_lock, users_table
from app.schemas.user import UserCreate, UserInDB, UserRole, UserUpdate


def _normalize_row(row: dict) -> dict:
    data = dict(row)
    role = normalize_role(data.get("role") or data.get("role_id"))
    data["role"] = role.value
    # TinyDB has no SQL FKs. role_id stores the Role.code/id reference independently
    # of department_id, matching the specialized assignment axes.
    data["role_id"] = role.value
    if "department_id" not in data:
        data["department_id"] = None
    return data


def _row_to_user(row: dict) -> UserInDB:
    normalized = _normalize_row(row)
    user = UserInDB.model_validate(normalized)
    stored_role_id = row.get("role_id")
    if (
        normalized.get("role") != row.get("role")
        or stored_role_id != user.role.value
        or "department_id" not in row
    ):
        users_table().update(
            {
                "role": user.role.value,
                "role_id": user.role.value,
                "department_id": user.department_id,
            },
            Query().id == user.id,
        )
    return user


def create_user(
    payload: UserCreate,
    *,
    role: UserRole = UserRole.employee,
    department_id: str | None = None,
) -> UserInDB:
    canonical_email = str(payload.email).lower()
    assigned_role = normalize_role(role)
    # TinyDB file I/O is locked per read/write only. Uniqueness must hold the
    # identity mutation lock across get and insert or overlapping creates of
    # the same canonical email both insert.
    with identity_mutation_lock():
        table = users_table()
        User = Query()
        if table.get(User.email == canonical_email):
            raise ValueError("A user with this email already exists.")
        if not is_known_department(department_id):
            raise ValueError("Unknown department")

        user = UserInDB(
            id=str(uuid4()),
            email=canonical_email,
            hashed_password=hash_password(payload.password),
            is_active=True,
            role=assigned_role,
            role_id=assigned_role,
            department_id=department_id,
            created_at=datetime.now(UTC),
        )
        table.insert(user.model_dump(mode="json"))
        return user


def get_user_by_id(user_id: str) -> UserInDB | None:
    row = users_table().get(Query().id == user_id)
    return _row_to_user(row) if row else None


def get_user_by_email(email: str) -> UserInDB | None:
    row = users_table().get(Query().email == email.lower())
    return _row_to_user(row) if row else None


def list_users() -> list[UserInDB]:
    return [_row_to_user(row) for row in users_table().all()]


def update_user(user_id: str, payload: UserUpdate) -> UserInDB | None:
    table = users_table()
    User = Query()
    updates = payload.model_dump(exclude_unset=True)
    if "password" in updates:
        plain = updates.pop("password")
        if plain is not None:
            updates["hashed_password"] = hash_password(plain)

    with identity_mutation_lock():
        existing = table.get(User.id == user_id)
        if not existing:
            return None

        if "email" in updates and updates["email"] is not None:
            new_email = str(updates["email"]).lower()
            conflict = table.get((User.email == new_email) & (User.id != user_id))
            if conflict:
                raise ValueError("A user with this email already exists.")
            updates["email"] = new_email
        if "role" in updates and updates["role"] is not None:
            assigned_role = normalize_role(updates["role"]).value
            updates["role"] = assigned_role
            updates["role_id"] = assigned_role
        if "department_id" in updates:
            department_id = updates["department_id"]
            if not is_known_department(department_id):
                raise ValueError("Unknown department")
            updates["department_id"] = department_id

        table.update(updates, User.id == user_id)
        refreshed = table.get(User.id == user_id)
        return _row_to_user(refreshed) if refreshed else None


def delete_user(user_id: str) -> bool:
    removed = users_table().remove(Query().id == user_id)
    return bool(removed)
