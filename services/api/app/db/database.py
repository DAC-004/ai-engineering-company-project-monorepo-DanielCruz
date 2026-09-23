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


def _ensure_inventory_capture_columns(engine) -> None:
    """
    Add capture-phase columns on already-created tables.

    SQLModel create_all does not ALTER existing databases. These columns are
    required so mandatory telemetry can be computed without dropping inventory.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    statements: list[str] = []

    if "medical_supply" in table_names:
        supply_columns = {column["name"] for column in inspector.get_columns("medical_supply")}
        if "minimum_stock" not in supply_columns:
            statements.append(
                "ALTER TABLE medical_supply ADD COLUMN minimum_stock INTEGER DEFAULT 10 NOT NULL"
            )
        if "expiry_date" not in supply_columns:
            statements.append("ALTER TABLE medical_supply ADD COLUMN expiry_date DATE")

    if "supply_consumption" in table_names:
        consumption_columns = {
            column["name"] for column in inspector.get_columns("supply_consumption")
        }
        if "department" not in consumption_columns:
            statements.append(
                "ALTER TABLE supply_consumption ADD COLUMN department VARCHAR(64) DEFAULT 'primary_care'"
            )

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        if "medical_supply" in table_names:
            connection.execute(
                text(
                    "UPDATE medical_supply SET expiry_date = '2026-09-12' "
                    "WHERE sku = 'HCR-MED-001' AND expiry_date IS NULL"
                )
            )


def init_databases() -> None:
    """
    Open both stores and create inventory tables.

    TinyDB is used only for users/auth. SQLModel.metadata.create_all builds
    MedicalSupply, SupplyDelivery, SupplyConsumption, and TaskFailure tables
    on the DATABASE_URL engine (Supabase in the live app).
    """
    get_tinydb()
    # Register table models on SQLModel.metadata before create_all.
    from app.models import (  # noqa: F401
        MedicalSupply,
        SupplyConsumption,
        SupplyDelivery,
        TaskFailure,
    )

    SQLModel.metadata.create_all(get_engine())
    _ensure_inventory_capture_columns(get_engine())
