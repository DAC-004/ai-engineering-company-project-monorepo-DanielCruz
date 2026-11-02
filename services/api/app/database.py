"""TinyDB persistence for the HealthCore Supplier Directory."""

from __future__ import annotations

import os
from pathlib import Path

from tinydb import TinyDB
from tinydb.table import Table

from shared.healthcore_rag.config import runtime_data_path

# The host store is used only when its own directory exists. A checkout
# without that directory keeps the file beside the API package.
_default_db_path = runtime_data_path(
    Path("/var/lib/healthcore/suppliers/suppliers.json"),
    Path(__file__).resolve().parent.parent / "data" / "suppliers.json",
)
_db: TinyDB | None = None
_open_path: Path | None = None

_suppliers_override = os.environ.get("SUPPLIERS_DB_PATH")
DB_PATH = Path(_suppliers_override) if _suppliers_override else _default_db_path
DATA_DIR = DB_PATH.parent


def _resolved_db_path() -> Path:
    override = os.environ.get("SUPPLIERS_DB_PATH")
    if override:
        return Path(override)
    return DB_PATH


def ensure_data_dir() -> None:
    _resolved_db_path().parent.mkdir(parents=True, exist_ok=True)


def get_db() -> TinyDB:
    global _db, _open_path
    path = _resolved_db_path()
    if _db is not None and _open_path != path:
        close_db()
    if _db is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        _db = TinyDB(path)
        _open_path = path
        # TinyDB creates the file with the process umask. The directory is
        # the service account's. The file itself stays group-readable only.
        if path.exists():
            path.chmod(0o640)
    return _db


def get_suppliers_table() -> Table:
    return get_db().table("suppliers")


def close_db() -> None:
    global _db, _open_path
    if _db is not None:
        _db.close()
        _db = None
        _open_path = None
