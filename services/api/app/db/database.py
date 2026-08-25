"""Dual-database initialization: TinyDB identity plus SQLModel/Supabase inventory.

`get_db` yields one SQLModel Session per request. There is no module-level
session. TinyDB keeps its own client in app.db.tinydb (auth only).
"""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings
from app.db.tinydb import get_db as get_tinydb

_engine = None


def _normalize_database_url(url: str) -> str:
    """Accept postgres:// URIs and map them to the SQLAlchemy postgresql scheme."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def get_engine():
    """Return the process-wide SQLModel engine (connection pool, not a session)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        url = _normalize_database_url(settings.database_url)
        connect_args = {}
        engine_kwargs: dict = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            engine_kwargs["connect_args"] = connect_args
        _engine = create_engine(url, **engine_kwargs)
    return _engine


def reset_engine_for_tests() -> None:
    """Dispose the cached engine so tests can point DATABASE_URL at an isolated file."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one SQLModel session per request, closed afterwards."""
    with Session(get_engine()) as session:
        yield session


def init_databases() -> None:
    """
    Open both stores and create inventory tables.

    TinyDB is used only for users/auth. SQLModel.metadata.create_all builds
    MedicalSupply, SupplyDelivery, and SupplyConsumption tables on the
    DATABASE_URL engine (Supabase in the live app).
    """
    get_tinydb()
    # Register table models on SQLModel.metadata before create_all.
    from app import models as _inventory_models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())
