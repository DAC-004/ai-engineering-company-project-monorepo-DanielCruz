"""TinyDB persistence for the HealthCore Supplier Directory."""

from __future__ import annotations

from pathlib import Path

from tinydb import TinyDB
from tinydb.table import Table

# Persist beside the API package so restarts keep supplier records on disk.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "suppliers.json"

_db: TinyDB | None = None


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_db() -> TinyDB:
    global _db
    if _db is None:
        ensure_data_dir()
        _db = TinyDB(DB_PATH)
    return _db


def get_suppliers_table() -> Table:
    return get_db().table("suppliers")


def close_db() -> None:
    global _db
    if _db is not None:
        _db.close()
        _db = None
