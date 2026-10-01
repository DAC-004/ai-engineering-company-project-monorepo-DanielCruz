"""Dual-database initialization: TinyDB identity plus SQLModel/Supabase inventory.

`get_db` yields one SQLModel Session per request. There is no module-level
session. TinyDB keeps its own client in app.db.tinydb (auth only).
"""

from __future__ import annotations

from collections.abc import Generator
from urllib.parse import quote, urlsplit

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings
from app.db.tinydb import get_db as get_tinydb

_engine = None


def _normalize_database_url(url: str) -> str:
    """Accept postgres:// URIs and keep password characters from splitting the host.

    A raw ``#`` in a Supabase password is a URI fragment, so the host never
    resolves. Quote the password only when it still contains those reserved
    characters. An already encoded password is left unchanged.
    """
    url = url.strip()
    # A pasted dashboard URI can leave the example scheme in front of the real URI.
    lowered = url.lower()
    for prefix in ("postgresql:", "postgres:"):
        remainder = lowered[len(prefix) :]
        if lowered.startswith(prefix) and remainder.startswith(("postgresql://", "postgres://")):
            url = url[len(prefix) :]
            lowered = url.lower()
            break
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    userinfo, hostpart = rest.rsplit("@", 1)
    if ":" not in userinfo:
        return f"{scheme}://{userinfo}@{hostpart}"
    user, password = userinfo.split(":", 1)
    if any(character in password for character in "#@:/? "):
        password = quote(password, safe="")
    # The transaction-pooler port does not accept connections on the direct
    # Supabase host. That host serves the database on 5432.
    parsed = urlsplit(f"{scheme}://{user}:{password}@{hostpart}")
    hostname = parsed.hostname or ""
    if hostname.startswith("db.") and hostname.endswith(".supabase.co") and parsed.port == 6543:
        hostpart = hostpart.replace(":6543", ":5432", 1)
    return f"{scheme}://{user}:{password}@{hostpart}"


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


def _ensure_rfp_response_columns(engine) -> None:
    """Add Part 2 columns when the RFP tables already exist.

    create_all does not alter a database created by Part 1. New databases
    receive the columns from the models. This only fills a missing column.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    statements: list[str] = []
    boolean_default = "FALSE" if engine.dialect.name == "postgresql" else "0"

    if "rfp_ticket" in table_names:
        ticket_columns = {column["name"] for column in inspector.get_columns("rfp_ticket")}
        if "part3_handoff" not in ticket_columns:
            statements.append("ALTER TABLE rfp_ticket ADD COLUMN part3_handoff JSON")

    if "rfp_department_section" in table_names:
        section_columns = {column["name"] for column in inspector.get_columns("rfp_department_section")}
        if "draft_content" not in section_columns:
            statements.append("ALTER TABLE rfp_department_section ADD COLUMN draft_content TEXT")
        if "evaluation_results" not in section_columns:
            statements.append("ALTER TABLE rfp_department_section ADD COLUMN evaluation_results JSON")
        if "needs_human_review" not in section_columns:
            statements.append(
                "ALTER TABLE rfp_department_section "
                f"ADD COLUMN needs_human_review BOOLEAN NOT NULL DEFAULT {boolean_default}"
            )
        if "approval_status" not in section_columns:
            statements.append("ALTER TABLE rfp_department_section ADD COLUMN approval_status VARCHAR(32)")
        if "approver" not in section_columns:
            statements.append("ALTER TABLE rfp_department_section ADD COLUMN approver VARCHAR(200)")
        if "approved_at" not in section_columns:
            statements.append("ALTER TABLE rfp_department_section ADD COLUMN approved_at TIMESTAMP")
        if "approved_content_sha256" not in section_columns:
            statements.append("ALTER TABLE rfp_department_section ADD COLUMN approved_content_sha256 VARCHAR(64)")
        if "submitted_by_user_id" not in section_columns:
            statements.append("ALTER TABLE rfp_department_section ADD COLUMN submitted_by_user_id VARCHAR(36)")
        if "approval_revision_count" not in section_columns:
            statements.append(
                "ALTER TABLE rfp_department_section "
                "ADD COLUMN approval_revision_count INTEGER NOT NULL DEFAULT 0"
            )
        if "iteration_limit_reached" not in section_columns:
            statements.append(
                "ALTER TABLE rfp_department_section "
                f"ADD COLUMN iteration_limit_reached BOOLEAN NOT NULL DEFAULT {boolean_default}"
            )

    if "rfp_ticket" in table_names:
        ticket_columns = {column["name"] for column in inspector.get_columns("rfp_ticket")}
        if "node_trace" not in ticket_columns:
            statements.append("ALTER TABLE rfp_ticket ADD COLUMN node_trace JSON")
        if "arbitration_state" not in ticket_columns:
            statements.append("ALTER TABLE rfp_ticket ADD COLUMN arbitration_state JSON")

    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


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
    from app import rfp_models as _rfp_models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())
    _ensure_inventory_capture_columns(get_engine())
    _ensure_rfp_response_columns(get_engine())
