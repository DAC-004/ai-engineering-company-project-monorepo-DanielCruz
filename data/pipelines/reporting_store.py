"""Reporting-schema storage for the Monthly Clinic Supply Performance pipeline.

Creates ``reporting`` tables, records run metadata, and upserts clinic-month
rows. Never writes to ``telemetry_events``.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

from data.pipelines.transforms import (
    V1_EVENT_TYPES,
    fill_zero_clinic_rows,
    month_window,
)


class SourceUnavailableError(RuntimeError):
    """Raised when ``telemetry_events`` is missing and the pipeline must not publish zeros."""


class OverlappingPipelineRunError(RuntimeError):
    """Raised when another run already holds the clinic-month lock or Running row."""


def qualify(engine: Engine, table_name: str) -> str:
    if engine.dialect.name == "postgresql":
        return f"reporting.{table_name}"
    return table_name


def ensure_reporting_tables(engine: Engine) -> None:
    """Create the reporting schema and control tables if they do not exist."""
    if engine.dialect.name == "postgresql":
        ddl = [
            "CREATE SCHEMA IF NOT EXISTS reporting",
            """
            CREATE TABLE IF NOT EXISTS reporting.monthly_clinic_supply_performance (
              id uuid PRIMARY KEY,
              clinic_id text NOT NULL,
              country text NOT NULL,
              month_start date NOT NULL,
              total_supply_cost numeric NOT NULL DEFAULT 0,
              supply_consumption_count integer NOT NULL DEFAULT 0,
              critical_stockout_count integer NOT NULL DEFAULT 0,
              expiry_risk_count integer NOT NULL DEFAULT 0,
              currency text NOT NULL,
              computed_at timestamptz NOT NULL DEFAULT now(),
              UNIQUE (clinic_id, month_start)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS reporting.monthly_clinic_supply_performance_history (
              history_id uuid PRIMARY KEY,
              run_id uuid NOT NULL,
              replaced_at timestamptz NOT NULL,
              clinic_id text NOT NULL,
              country text NOT NULL,
              month_start date NOT NULL,
              total_supply_cost numeric NOT NULL,
              supply_consumption_count integer NOT NULL,
              critical_stockout_count integer NOT NULL,
              expiry_risk_count integer NOT NULL,
              currency text NOT NULL,
              previous_computed_at timestamptz
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS reporting.pipeline_runs (
              run_id uuid PRIMARY KEY,
              started_at timestamptz NOT NULL,
              finished_at timestamptz,
              status text NOT NULL,
              records_extracted integer NOT NULL DEFAULT 0,
              records_loaded integer NOT NULL DEFAULT 0,
              records_rejected integer NOT NULL DEFAULT 0,
              error_message text,
              month_start date NOT NULL,
              trigger_type text NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS reporting.pipeline_watermarks (
              month_start date PRIMARY KEY,
              last_ingested_at timestamptz,
              updated_at timestamptz NOT NULL
            )
            """,
        ]
    else:
        ddl = [
            """
            CREATE TABLE IF NOT EXISTS monthly_clinic_supply_performance (
              id TEXT PRIMARY KEY,
              clinic_id TEXT NOT NULL,
              country TEXT NOT NULL,
              month_start DATE NOT NULL,
              total_supply_cost NUMERIC NOT NULL DEFAULT 0,
              supply_consumption_count INTEGER NOT NULL DEFAULT 0,
              critical_stockout_count INTEGER NOT NULL DEFAULT 0,
              expiry_risk_count INTEGER NOT NULL DEFAULT 0,
              currency TEXT NOT NULL,
              computed_at TEXT NOT NULL,
              UNIQUE (clinic_id, month_start)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS monthly_clinic_supply_performance_history (
              history_id TEXT PRIMARY KEY,
              run_id TEXT NOT NULL,
              replaced_at TEXT NOT NULL,
              clinic_id TEXT NOT NULL,
              country TEXT NOT NULL,
              month_start DATE NOT NULL,
              total_supply_cost NUMERIC NOT NULL,
              supply_consumption_count INTEGER NOT NULL,
              critical_stockout_count INTEGER NOT NULL,
              expiry_risk_count INTEGER NOT NULL,
              currency TEXT NOT NULL,
              previous_computed_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pipeline_runs (
              run_id TEXT PRIMARY KEY,
              started_at TEXT NOT NULL,
              finished_at TEXT,
              status TEXT NOT NULL,
              records_extracted INTEGER NOT NULL DEFAULT 0,
              records_loaded INTEGER NOT NULL DEFAULT 0,
              records_rejected INTEGER NOT NULL DEFAULT 0,
              error_message TEXT,
              month_start DATE NOT NULL,
              trigger_type TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pipeline_watermarks (
              month_start DATE PRIMARY KEY,
              last_ingested_at TEXT,
              updated_at TEXT NOT NULL
            )
            """,
        ]
    with engine.begin() as connection:
        for statement in ddl:
            connection.execute(text(statement))


def telemetry_events_available(engine: Engine) -> bool:
    inspector = inspect(engine)
    return "telemetry_events" in set(inspector.get_table_names())


def _parse_tags(raw_tags: Any) -> dict[str, Any]:
    if raw_tags is None:
        return {}
    if isinstance(raw_tags, dict):
        return raw_tags
    if isinstance(raw_tags, str):
        stripped = raw_tags.strip()
        if not stripped:
            return {}
        loaded = json.loads(stripped)
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _as_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError("timestamp must be datetime or ISO string")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def extract_supply_performance_events(engine: Engine, month_start: date) -> list[dict[str, Any]]:
    """Read-only extract of the four v1 event types for one UTC month.

    Physical source columns are ``timestamp``, ``event_type``, and ``tags``.
    ``user_id`` is not selected. Supply cost is ``tags.total_cost``.
    """
    if not telemetry_events_available(engine):
        raise SourceUnavailableError("telemetry_events table is not available")

    window_start, window_end = month_window(month_start)
    event_types = tuple(sorted(V1_EVENT_TYPES))
    placeholders = ", ".join(f":event_type_{index}" for index, _ in enumerate(event_types))
    params: dict[str, Any] = {
        "window_start": window_start,
        "window_end": window_end,
    }
    for index, event_type in enumerate(event_types):
        params[f"event_type_{index}"] = event_type

    statement = text(
        f"""
        SELECT event_id, timestamp, event_type, tags
        FROM telemetry_events
        WHERE event_type IN ({placeholders})
          AND timestamp >= :window_start
          AND timestamp < :window_end
        ORDER BY timestamp ASC, event_id ASC
        """
    )
    events: list[dict[str, Any]] = []
    with engine.connect() as connection:
        rows = connection.execute(statement, params)
        for row in rows:
            events.append(
                {
                    "event_id": row.event_id,
                    "timestamp": _as_utc(row.timestamp),
                    "event_type": row.event_type,
                    "tags": _parse_tags(row.tags),
                }
            )
    return events


def _lock_key(month_start: date) -> int:
    return month_start.year * 100 + month_start.month


def _acquire_month_lock(connection: Connection, month_start: date) -> None:
    if connection.dialect.name != "postgresql":
        return
    acquired = connection.execute(
        text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
        {"lock_key": _lock_key(month_start)},
    ).scalar()
    if not acquired:
        raise OverlappingPipelineRunError(
            f"overlapping_run for month_start={month_start.isoformat()}"
        )


def start_pipeline_run(
    engine: Engine,
    month_start: date,
    trigger_type: str,
) -> str:
    ensure_reporting_tables(engine)
    runs = qualify(engine, "pipeline_runs")
    run_id = str(uuid4())
    started_at = datetime.now(UTC).isoformat()
    with engine.begin() as connection:
        running = connection.execute(
            text(
                f"""
                SELECT run_id FROM {runs}
                WHERE month_start = :month_start AND status = 'Running'
                """
            ),
            {"month_start": month_start.isoformat()},
        ).first()
        if running is not None:
            raise OverlappingPipelineRunError(
                f"overlapping_run for month_start={month_start.isoformat()}"
            )
        connection.execute(
            text(
                f"""
                INSERT INTO {runs} (
                    run_id, started_at, finished_at, status,
                    records_extracted, records_loaded, records_rejected,
                    error_message, month_start, trigger_type
                ) VALUES (
                    :run_id, :started_at, NULL, 'Running',
                    0, 0, 0, NULL, :month_start, :trigger_type
                )
                """
            ),
            {
                "run_id": run_id,
                "started_at": started_at,
                "month_start": month_start.isoformat(),
                "trigger_type": trigger_type,
            },
        )
    return run_id


def finish_pipeline_run(
    engine: Engine,
    run_id: str,
    *,
    status: str,
    records_extracted: int = 0,
    records_loaded: int = 0,
    records_rejected: int = 0,
    error_message: str | None = None,
) -> None:
    runs = qualify(engine, "pipeline_runs")
    with engine.begin() as connection:
        connection.execute(
            text(
                f"""
                UPDATE {runs}
                SET finished_at = :finished_at,
                    status = :status,
                    records_extracted = :records_extracted,
                    records_loaded = :records_loaded,
                    records_rejected = :records_rejected,
                    error_message = :error_message
                WHERE run_id = :run_id
                """
            ),
            {
                "run_id": run_id,
                "finished_at": datetime.now(UTC).isoformat(),
                "status": status,
                "records_extracted": records_extracted,
                "records_loaded": records_loaded,
                "records_rejected": records_rejected,
                "error_message": error_message,
            },
        )


def load_monthly_clinic_supply_performance(
    engine: Engine,
    *,
    aggregates: list[dict[str, Any]],
    run_id: str,
    month_start: date,
    max_event_timestamp: datetime | None,
) -> int:
    """Idempotent upsert keyed on ``(clinic_id, month_start)``. One transaction."""
    ensure_reporting_tables(engine)
    dest = qualify(engine, "monthly_clinic_supply_performance")
    history = qualify(engine, "monthly_clinic_supply_performance_history")
    watermarks = qualify(engine, "pipeline_watermarks")
    rows = fill_zero_clinic_rows(aggregates, month_start)
    computed_at = datetime.now(UTC).isoformat()
    watermark_ts = (
        max_event_timestamp.isoformat() if max_event_timestamp is not None else computed_at
    )

    with engine.begin() as connection:
        _acquire_month_lock(connection, month_start)
        existing = connection.execute(
            text(
                f"""
                SELECT clinic_id, country, month_start, total_supply_cost,
                       supply_consumption_count, critical_stockout_count,
                       expiry_risk_count, currency, computed_at
                FROM {dest}
                WHERE month_start = :month_start
                """
            ),
            {"month_start": month_start.isoformat()},
        ).mappings()
        existing_by_clinic = {row["clinic_id"]: dict(row) for row in existing}

        for clinic_id, previous in existing_by_clinic.items():
            connection.execute(
                text(
                    f"""
                    INSERT INTO {history} (
                        history_id, run_id, replaced_at, clinic_id, country,
                        month_start, total_supply_cost, supply_consumption_count,
                        critical_stockout_count, expiry_risk_count, currency,
                        previous_computed_at
                    ) VALUES (
                        :history_id, :run_id, :replaced_at, :clinic_id, :country,
                        :month_start, :total_supply_cost, :supply_consumption_count,
                        :critical_stockout_count, :expiry_risk_count, :currency,
                        :previous_computed_at
                    )
                    """
                ),
                {
                    "history_id": str(uuid4()),
                    "run_id": run_id,
                    "replaced_at": computed_at,
                    "clinic_id": previous["clinic_id"],
                    "country": previous["country"],
                    "month_start": month_start.isoformat(),
                    "total_supply_cost": previous["total_supply_cost"],
                    "supply_consumption_count": previous["supply_consumption_count"],
                    "critical_stockout_count": previous["critical_stockout_count"],
                    "expiry_risk_count": previous["expiry_risk_count"],
                    "currency": previous["currency"],
                    "previous_computed_at": str(previous["computed_at"]),
                },
            )

        for row in rows:
            connection.execute(
                text(
                    f"""
                    INSERT INTO {dest} (
                        id, clinic_id, country, month_start, total_supply_cost,
                        supply_consumption_count, critical_stockout_count,
                        expiry_risk_count, currency, computed_at
                    ) VALUES (
                        :id, :clinic_id, :country, :month_start, :total_supply_cost,
                        :supply_consumption_count, :critical_stockout_count,
                        :expiry_risk_count, :currency, :computed_at
                    )
                    ON CONFLICT (clinic_id, month_start) DO UPDATE SET
                        country = excluded.country,
                        total_supply_cost = excluded.total_supply_cost,
                        supply_consumption_count = excluded.supply_consumption_count,
                        critical_stockout_count = excluded.critical_stockout_count,
                        expiry_risk_count = excluded.expiry_risk_count,
                        currency = excluded.currency,
                        computed_at = excluded.computed_at
                    """
                ),
                {
                    "id": str(uuid4()),
                    "clinic_id": row["clinic_id"],
                    "country": row["country"],
                    "month_start": month_start.isoformat(),
                    "total_supply_cost": str(row["total_supply_cost"]),
                    "supply_consumption_count": row["supply_consumption_count"],
                    "critical_stockout_count": row["critical_stockout_count"],
                    "expiry_risk_count": row["expiry_risk_count"],
                    "currency": row["currency"],
                    "computed_at": computed_at,
                },
            )

        connection.execute(
            text(
                f"""
                INSERT INTO {watermarks} (month_start, last_ingested_at, updated_at)
                VALUES (:month_start, :last_ingested_at, :updated_at)
                ON CONFLICT (month_start) DO UPDATE SET
                    last_ingested_at = excluded.last_ingested_at,
                    updated_at = excluded.updated_at
                """
            ),
            {
                "month_start": month_start.isoformat(),
                "last_ingested_at": watermark_ts,
                "updated_at": computed_at,
            },
        )
    return len(rows)


def _as_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    raise TypeError("month_start must be a date")


def _cost_number(value: Any) -> float:
    return float(Decimal(str(value)))


def get_monthly_clinic_supply_performance(
    engine: Engine,
    month_start: date | None = None,
) -> dict[str, Any] | None:
    """Read published board rows. Does not extract or transform."""
    ensure_reporting_tables(engine)
    dest = qualify(engine, "monthly_clinic_supply_performance")
    runs = qualify(engine, "pipeline_runs")
    with engine.connect() as connection:
        resolved = month_start
        if resolved is None:
            latest = connection.execute(
                text(
                    f"""
                    SELECT month_start FROM {runs}
                    WHERE status = 'Completed'
                    ORDER BY month_start DESC, started_at DESC
                    LIMIT 1
                    """
                )
            ).first()
            if latest is None:
                return None
            resolved = _as_date(latest.month_start)
        rows = connection.execute(
            text(
                f"""
                SELECT clinic_id, country, total_supply_cost,
                       supply_consumption_count, critical_stockout_count,
                       expiry_risk_count, currency
                FROM {dest}
                WHERE month_start = :month_start
                ORDER BY CAST(clinic_id AS INTEGER)
                """
            ),
            {"month_start": resolved.isoformat()},
        ).mappings()
        clinics = [
            {
                "clinic_id": row["clinic_id"],
                "country": row["country"],
                "total_supply_cost": _cost_number(row["total_supply_cost"]),
                "supply_consumption_count": int(row["supply_consumption_count"]),
                "critical_stockout_count": int(row["critical_stockout_count"]),
                "expiry_risk_count": int(row["expiry_risk_count"]),
                "currency": row["currency"],
            }
            for row in rows
        ]
        if not clinics:
            completed = connection.execute(
                text(
                    f"""
                    SELECT run_id FROM {runs}
                    WHERE status = 'Completed' AND month_start = :month_start
                    LIMIT 1
                    """
                ),
                {"month_start": resolved.isoformat()},
            ).first()
            if completed is None:
                return None
        return {"month_start": resolved.isoformat(), "clinics": clinics}


def get_latest_pipeline_run(engine: Engine) -> dict[str, Any] | None:
    ensure_reporting_tables(engine)
    runs = qualify(engine, "pipeline_runs")
    with engine.connect() as connection:
        row = connection.execute(
            text(
                f"""
                SELECT run_id, started_at, finished_at, status,
                       records_extracted, records_loaded, records_rejected,
                       error_message, month_start, trigger_type
                FROM {runs}
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
        ).mappings().first()
    if row is None:
        return None
    records_extracted = int(row["records_extracted"])
    return {
        "run_id": row["run_id"],
        "status": row["status"],
        "started_at": str(row["started_at"]),
        "finished_at": None if row["finished_at"] is None else str(row["finished_at"]),
        "records_processed": records_extracted,
        "records_extracted": records_extracted,
        "records_loaded": int(row["records_loaded"]),
        "records_rejected": int(row["records_rejected"]),
        "month_start": _as_date(row["month_start"]).isoformat(),
        "trigger_type": row["trigger_type"],
        "error_message": row["error_message"],
    }


def get_pipeline_run(engine: Engine, run_id: str) -> dict[str, Any] | None:
    ensure_reporting_tables(engine)
    runs = qualify(engine, "pipeline_runs")
    with engine.connect() as connection:
        row = connection.execute(
            text(
                f"""
                SELECT run_id, started_at, finished_at, status,
                       records_extracted, records_loaded, records_rejected,
                       error_message, month_start, trigger_type
                FROM {runs}
                WHERE run_id = :run_id
                """
            ),
            {"run_id": run_id},
        ).mappings().first()
    if row is None:
        return None
    records_extracted = int(row["records_extracted"])
    return {
        "run_id": row["run_id"],
        "status": row["status"],
        "started_at": str(row["started_at"]),
        "finished_at": None if row["finished_at"] is None else str(row["finished_at"]),
        "records_processed": records_extracted,
        "records_extracted": records_extracted,
        "records_loaded": int(row["records_loaded"]),
        "records_rejected": int(row["records_rejected"]),
        "month_start": _as_date(row["month_start"]).isoformat(),
        "trigger_type": row["trigger_type"],
        "error_message": row["error_message"],
    }
