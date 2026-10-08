"""TinyDB persistence for the HealthCore Supplier Directory."""

from __future__ import annotations

from pathlib import Path

from tinydb import TinyDB
from tinydb.table import Table

from shared.healthcore_rag.config import runtime_data_path

# The host store is used only when its own directory exists. A checkout
# without that directory keeps the file beside the API package.
DB_PATH = runtime_data_path(
    Path("/var/lib/healthcore/suppliers/suppliers.json"),
    Path(__file__).resolve().parent.parent / "data" / "suppliers.json",
)
DATA_DIR = DB_PATH.parent

_db: TinyDB | None = None


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_db() -> TinyDB:
    global _db
    if _db is None:
        ensure_data_dir()
        _db = TinyDB(DB_PATH)
        # TinyDB creates the file with the process umask. The directory is
        # the service account's. The file itself stays group-readable only.
        if DB_PATH.exists():
            DB_PATH.chmod(0o640)
    return _db


def get_suppliers_table() -> Table:
    return get_db().table("suppliers")


def close_db() -> None:
    global _db
    if _db is not None:
        _db.close()
        _db = None
