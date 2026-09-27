"""TinyDB persistence for authentication Users/Profiles and incidents."""

from __future__ import annotations

from pathlib import Path

from tinydb import TinyDB

from app.core.config import get_settings

_db: TinyDB | None = None


def get_db() -> TinyDB:
    """Return the shared TinyDB instance for identity data and incidents."""
    global _db
    if _db is None:
        path = Path(get_settings().tinydb_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        _db = TinyDB(path)
    return _db


def users_table():
    return get_db().table("users")


def profiles_table():
    return get_db().table("profiles")


def incidents_table():
    return get_db().table("incidents")


def incident_seed_keys_table():
    """Derived seed markers only. Never stores a raw CSV incident_id."""
    return get_db().table("incident_seed_keys")


def reset_db_for_tests() -> None:
    """Close and discard the cached DB handle (tests / isolated validation runs)."""
    global _db
    if _db is not None:
        _db.close()
        _db = None
