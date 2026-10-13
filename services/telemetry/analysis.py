"""Operational telemetry metrics calculated with SQL load and Pandas aggregation.

Stored HealthCore events keep the capture envelope's ``properties`` object in the
``tags`` JSON column. Metric functions read that stored shape and do not invent
business KPIs such as sales, conversion, or revenue.

Each public metric function is side-effect free, accepts the endpoint-resolved
UTC window, and follows: load (SQL) -> refine (Pandas) -> convert types ->
group -> aggregate -> serialise.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

# Catalogue events that are themselves failure or interruption signals.
_FAILURE_EVENT_TYPES = (
    "user_login_failed",
    "frontend_error_uncaught",
    "authorization_denied",
    "outbound_order_rejected",
    "session_expired",
    "direct_stock_edit_rejected",
)
_API_ERROR_OUTCOMES = ("client_error", "server_error")


def _isoformat_utc(moment: datetime) -> str:
    """Serialize a timezone-aware instant as ISO 8601 UTC with a Z suffix."""
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _json_scalar(value: object) -> object:
    """Convert NumPy / pandas scalars so ``json.dumps`` can serialize records."""
    item = getattr(value, "item", None)
    if callable(item):
        return item()
    if isinstance(value, datetime):
        return _isoformat_utc(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _parse_tags(value: object) -> dict[str, Any]:
    """Normalize a stored ``tags`` value to a dict (PostgreSQL JSON or SQLite text)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        loaded = json.loads(stripped)
        if isinstance(loaded, dict):
            return loaded
        return {}
    return {}


def _expand_tags(events_frame: pd.DataFrame) -> pd.DataFrame:
    """Attach tag dimensions as columns. Missing keys become null and are dropped later."""
    tags_frame = pd.json_normalize(events_frame["tags"].map(_parse_tags))
    tags_frame.index = events_frame.index
    return pd.concat([events_frame.drop(columns=["tags"]), tags_frame], axis=1)


def events_per_day(
    start_date: datetime,
    end_date: datetime,
    *,
    engine: Engine,
) -> list[dict[str, Any]]:
    """Daily event volume by ``event_type``.

    Operational question: how many telemetry events of each type occurred on
    each UTC day in the requested window?
    """
    load_sql = text(
        """
        SELECT timestamp, event_type
        FROM telemetry_events
        WHERE timestamp >= :start_date
          AND timestamp < :end_date
        """
    )
    with engine.connect() as connection:
        events_frame = pd.read_sql(
            load_sql,
            connection,
            params={"start_date": start_date, "end_date": end_date},
        )

    if events_frame.empty:
        return []

    refined_frame = events_frame.dropna(subset=["timestamp", "event_type"])
    refined_frame = refined_frame.copy()
    refined_frame["timestamp"] = pd.to_datetime(
        refined_frame["timestamp"], utc=True, format="mixed"
    )
    refined_frame["date"] = refined_frame["timestamp"].dt.strftime("%Y-%m-%d")

    volume_by_day_and_type = (
        refined_frame.groupby(["date", "event_type"])
        .agg(event_count=("event_type", "count"))
        .reset_index()
        .sort_values(["date", "event_type"], kind="mergesort")
    )
    return json.loads(
        json.dumps(volume_by_day_and_type.to_dict(orient="records"), default=_json_scalar)
    )


def error_rate_by_type(
    start_date: datetime,
    end_date: datetime,
    *,
    engine: Engine,
) -> list[dict[str, Any]]:
    """Daily within-type error rate for failure events and failed API calls.

    Operational question: for each UTC day and event type, what share of that
    type's events are errors or failures?

    ``is_error`` is derived after load: catalogue failure types are errors, and
    ``api_request_completed`` rows are errors when ``tags.outcome`` is a client
    or server error or ``tags.status_code`` is >= 400. All event types needed
    for that numerator and denominator are loaded in one query.
    """
    load_sql = text(
        """
        SELECT timestamp, event_type, tags
        FROM telemetry_events
        WHERE timestamp >= :start_date
          AND timestamp < :end_date
        """
    )
    with engine.connect() as connection:
        events_frame = pd.read_sql(
            load_sql,
            connection,
            params={"start_date": start_date, "end_date": end_date},
        )

    if events_frame.empty:
        return []

    refined_frame = _expand_tags(events_frame)
    refined_frame = refined_frame.dropna(subset=["timestamp", "event_type"])
    refined_frame = refined_frame.copy()

    if "outcome" not in refined_frame.columns:
        refined_frame["outcome"] = pd.NA
    if "status_code" not in refined_frame.columns:
        refined_frame["status_code"] = pd.NA

    refined_frame["status_code"] = pd.to_numeric(refined_frame["status_code"], errors="coerce")
    refined_frame["is_error"] = (
        refined_frame["event_type"].isin(_FAILURE_EVENT_TYPES)
        | (
            refined_frame["event_type"].eq("api_request_completed")
            & refined_frame["outcome"].isin(_API_ERROR_OUTCOMES)
        )
        | (
            refined_frame["event_type"].eq("api_request_completed")
            & (refined_frame["status_code"] >= 400)
        )
    )

    refined_frame["timestamp"] = pd.to_datetime(
        refined_frame["timestamp"], utc=True, format="mixed"
    )
    refined_frame["date"] = refined_frame["timestamp"].dt.strftime("%Y-%m-%d")

    rate_by_day_and_type = (
        refined_frame.groupby(["date", "event_type"])
        .agg(
            error_count=("is_error", "sum"),
            event_count=("event_type", "count"),
        )
        .reset_index()
    )
    rate_by_day_and_type["error_rate"] = (
        rate_by_day_and_type["error_count"] / rate_by_day_and_type["event_count"]
    )
    rate_by_day_and_type = rate_by_day_and_type.loc[
        rate_by_day_and_type["error_count"] > 0
    ].sort_values(["date", "event_type"], kind="mergesort")
    return json.loads(
        json.dumps(rate_by_day_and_type.to_dict(orient="records"), default=_json_scalar)
    )


def latency_by_route(
    start_date: datetime,
    end_date: datetime,
    *,
    engine: Engine,
) -> list[dict[str, Any]]:
    """Mean API latency per route template per UTC day.

    Operational question: which inventory and auth routes are slow, and how
    long do they take on each day?

    ``route_template`` and ``duration_ms`` are extracted from ``tags``. Rows
    missing either dimension are dropped before grouping.
    """
    load_sql = text(
        """
        SELECT timestamp, event_type, tags
        FROM telemetry_events
        WHERE timestamp >= :start_date
          AND timestamp < :end_date
          AND event_type = 'api_request_completed'
        """
    )
    with engine.connect() as connection:
        events_frame = pd.read_sql(
            load_sql,
            connection,
            params={"start_date": start_date, "end_date": end_date},
        )

    if events_frame.empty:
        return []

    refined_frame = _expand_tags(events_frame)
    if "duration_ms" not in refined_frame.columns:
        refined_frame["duration_ms"] = pd.NA
    if "route_template" not in refined_frame.columns:
        refined_frame["route_template"] = pd.NA

    refined_frame["duration_ms"] = pd.to_numeric(refined_frame["duration_ms"], errors="coerce")
    refined_frame = refined_frame.dropna(subset=["timestamp", "duration_ms", "route_template"])
    if refined_frame.empty:
        return []

    refined_frame = refined_frame.copy()
    refined_frame["timestamp"] = pd.to_datetime(
        refined_frame["timestamp"], utc=True, format="mixed"
    )
    refined_frame["date"] = refined_frame["timestamp"].dt.strftime("%Y-%m-%d")

    latency_by_day_and_route = (
        refined_frame.groupby(["date", "route_template"])
        .agg(
            request_count=("duration_ms", "count"),
            avg_duration_ms=("duration_ms", "mean"),
        )
        .reset_index()
        .sort_values(["date", "route_template"], kind="mergesort")
    )
    latency_by_day_and_route["avg_duration_ms"] = latency_by_day_and_route[
        "avg_duration_ms"
    ].round(2)
    return json.loads(
        json.dumps(latency_by_day_and_route.to_dict(orient="records"), default=_json_scalar)
    )


def build_telemetry_report(
    start_date: datetime,
    end_date: datetime,
    *,
    engine: Engine,
) -> dict[str, Any]:
    """Run every metric function against the same resolved UTC window."""
    return {
        "period": {
            "from": _isoformat_utc(start_date),
            "to": _isoformat_utc(end_date),
        },
        "metrics": {
            "events_per_day": events_per_day(start_date, end_date, engine=engine),
            "error_rate_by_type": error_rate_by_type(start_date, end_date, engine=engine),
            "latency_by_route": latency_by_route(start_date, end_date, engine=engine),
        },
    }
