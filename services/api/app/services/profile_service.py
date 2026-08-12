"""Profile service — TinyDB CRUD linked 1:1 to User via user_id."""

from __future__ import annotations

from uuid import uuid4

from tinydb import Query

from app.db.tinydb import profiles_table
from app.schemas.profile import ProfilePublic, ProfileUpdate


def _row_to_profile(row: dict) -> ProfilePublic:
    return ProfilePublic.model_validate(row)


def create_profile(
    *,
    user_id: str,
    name: str | None = None,
    phone: str | None = None,
    address: str | None = None,
) -> ProfilePublic:
    table = profiles_table()
    if table.get(Query().user_id == user_id):
        raise ValueError("A profile already exists for this user.")

    profile = ProfilePublic(
        id=str(uuid4()),
        user_id=user_id,
        name=name or "",
        phone=phone or "",
        address=address or "",
    )
    table.insert(profile.model_dump(mode="json"))
    return profile


def get_profile_by_user_id(user_id: str) -> ProfilePublic | None:
    row = profiles_table().get(Query().user_id == user_id)
    return _row_to_profile(row) if row else None


def update_profile_for_user(user_id: str, payload: ProfileUpdate) -> ProfilePublic | None:
    table = profiles_table()
    Profile = Query()
    existing = table.get(Profile.user_id == user_id)
    if not existing:
        return None

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return _row_to_profile(existing)

    table.update(updates, Profile.user_id == user_id)
    refreshed = table.get(Profile.user_id == user_id)
    return _row_to_profile(refreshed) if refreshed else None


def delete_profile_for_user(user_id: str) -> bool:
    removed = profiles_table().remove(Query().user_id == user_id)
    return bool(removed)
