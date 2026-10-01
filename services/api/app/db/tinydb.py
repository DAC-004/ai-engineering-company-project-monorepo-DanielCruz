"""TinyDB persistence for authentication Users and Profiles."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from tinydb import TinyDB
from tinydb.storages import JSONStorage

from app.core.config import get_settings

_db: TinyDB | None = None


class LockedJSONStorage(JSONStorage):
    """One lock around each full read and each full write of the shared handle.

    FastAPI runs synchronous auth calls on a thread pool. JSONStorage seeks
    that handle and then decodes it. Another request can move the cursor
    during a write, so json.load sees an empty buffer or a torn document
    and raises JSONDecodeError. The lock keeps one read or write intact.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._io_lock = threading.RLock()

    def read(self) -> dict[str, dict[str, Any]] | None:
        with self._io_lock:
            return super().read()

    def write(self, data: dict[str, dict[str, Any]]) -> None:
        with self._io_lock:
            super().write(data)


def get_db() -> TinyDB:
    """Return the shared TinyDB instance used only for User/Profile identity data."""
    global _db
    if _db is None:
        path = Path(get_settings().tinydb_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        _db = TinyDB(path, storage=LockedJSONStorage)
    return _db


def users_table():
    return get_db().table("users")


def profiles_table():
    return get_db().table("profiles")


def reset_db_for_tests() -> None:
    """Close and discard the cached DB handle (tests / isolated validation runs)."""
    global _db
    if _db is not None:
        _db.close()
        _db = None
