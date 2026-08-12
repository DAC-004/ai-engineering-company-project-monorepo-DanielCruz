"""User service — TinyDB CRUD for authentication accounts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from tinydb import Query

from app.core.security import hash_password
from app.db.tinydb import users_table
from app.schemas.user import UserCreate, UserInDB, UserRole, UserUpdate


def _row_to_user(row: dict) -> UserInDB:
    return UserInDB.model_validate(row)


def create_user(payload: UserCreate, *, role: UserRole = UserRole.user) -> UserInDB:
    table = users_table()
    User = Query()
    if table.get(User.email == str(payload.email).lower()):
        raise ValueError("A user with this email already exists.")

    user = UserInDB(
        id=str(uuid4()),
        email=str(payload.email).lower(),
        hashed_password=hash_password(payload.password),
        is_active=True,
        role=role,
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
    existing = table.get(User.id == user_id)
    if not existing:
        return None

    updates = payload.model_dump(exclude_unset=True)
    if "password" in updates:
        plain = updates.pop("password")
        if plain is not None:
            updates["hashed_password"] = hash_password(plain)
    if "email" in updates and updates["email"] is not None:
        new_email = str(updates["email"]).lower()
        conflict = table.get((User.email == new_email) & (User.id != user_id))
        if conflict:
            raise ValueError("A user with this email already exists.")
        updates["email"] = new_email
    if "role" in updates and updates["role"] is not None:
        updates["role"] = UserRole(updates["role"]).value

    table.update(updates, User.id == user_id)
    refreshed = table.get(User.id == user_id)
    return _row_to_user(refreshed) if refreshed else None


def delete_user(user_id: str) -> bool:
    removed = users_table().remove(Query().id == user_id)
    return bool(removed)
