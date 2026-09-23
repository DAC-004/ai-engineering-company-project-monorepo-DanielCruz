"""Write-only telemetry persistence: allowlists, timestamp conversion, one bulk insert.

TelemetryEvent stays the envelope contract. This module projects allowlisted
properties into tags and inserts accepted rows in a single statement.
ON CONFLICT DO NOTHING skips already-stored event_id values without UPDATE.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import Session

from app.models import TelemetryEventRecord
from app.schemas.telemetry import TelemetryEvent

# Closed catalogue from docs/telemetry/event-schemas.json (and frontend schema.ts).
# Unknown event_type values are not listed here and store tags={}.
TELEMETRY_TAG_ALLOWLIST: dict[str, frozenset[str]] = {
    "inbound_order_created": frozenset(
        {
            "clinic_id",
            "country",
            "product_id",
            "product_category",
            "quantity",
            "vendor_name",
            "inbound_order_id",
        }
    ),
    "outbound_order_created": frozenset(
        {
            "clinic_id",
            "country",
            "product_id",
            "product_category",
            "quantity",
            "department",
            "outbound_order_id",
            "consumption_reason",
        }
    ),
    "stock_threshold_triggered": frozenset(
        {
            "clinic_id",
            "country",
            "product_id",
            "product_category",
            "quantity",
            "minimum_stock",
            "triggering_outbound_order_id",
        }
    ),
    "direct_stock_edit_rejected": frozenset(
        {
            "clinic_id",
            "country",
            "product_id",
            "product_category",
            "quantity",
            "http_method",
            "route_template",
            "rejection_reason",
        }
    ),
    "supply_expiry_flagged": frozenset(
        {
            "clinic_id",
            "country",
            "product_id",
            "product_category",
            "quantity",
            "expiry_date",
            "days_until_expiry",
            "expiry_window_days",
        }
    ),
    "user_login_succeeded": frozenset({"auth_method", "role"}),
    "user_login_failed": frozenset({"failure_reason"}),
    "session_expired": frozenset({"expiry_source", "attempted_route"}),
    "user_logout_completed": frozenset({"logout_method"}),
    "authorization_denied": frozenset(
        {
            "http_method",
            "route_template",
            "status_code",
            "denial_reason",
        }
    ),
    "outbound_order_rejected": frozenset(
        {
            "clinic_id",
            "country",
            "product_id",
            "product_category",
            "quantity",
            "available_quantity",
            "rejection_reason",
            "department",
        }
    ),
    "api_request_completed": frozenset(
        {
            "http_method",
            "route_template",
            "status_code",
            "duration_ms",
            "outcome",
        }
    ),
    "page_load_completed": frozenset({"route", "duration_ms", "navigation_type"}),
    "frontend_error_uncaught": frozenset(
        {
            "error_name",
            "sanitized_message",
            "route",
            "stack_hash",
        }
    ),
    "page_viewed": frozenset({"route", "referrer_route"}),
    "inventory_flow_abandoned": frozenset(
        {
            "flow_name",
            "last_completed_step",
            "time_in_flow_ms",
            "clinic_id",
            "product_id",
        }
    ),
}


def parse_event_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 string to UTC. Naive values are treated as UTC.

    TelemetryEvent only requires a non-empty string. Conversion lives here so
    a bad timestamp rejects that event without changing the Pydantic model.
    """
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def project_tags(event_type: str, properties: dict[str, Any]) -> dict[str, Any]:
    """Keep allowlisted keys only. Unknown types and empty allowlists store {}."""
    allowed = TELEMETRY_TAG_ALLOWLIST.get(event_type)
    if not allowed:
        return {}
    return {key: value for key, value in properties.items() if key in allowed}


def _conflict_ignore_insert(table, dialect_name: str):
    """INSERT ... ON CONFLICT DO NOTHING. Never DO UPDATE."""
    if dialect_name == "postgresql":
        return postgresql_insert(table)
    if dialect_name == "sqlite":
        return sqlite_insert(table)
    raise RuntimeError("Telemetry bulk insert supports postgresql and sqlite only")


def bulk_insert_telemetry_events(session: Session, rows: list[dict[str, Any]]) -> int:
    """Insert accepted rows in one statement. Returns the number of rows actually stored.

    Conflict-skipped event_id values are not stored and must be counted as rejected
    by the caller (received - stored). Unexpected database errors propagate so the
    handler does not return HTTP 200 with false stored counts.
    """
    if not rows:
        return 0

    bind = session.get_bind()
    table = TelemetryEventRecord.__table__
    stmt = (
        _conflict_ignore_insert(table, bind.dialect.name)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(table.c.event_id)
    )
    try:
        result = session.execute(stmt)
        inserted_ids = list(result.scalars().all())
        session.commit()
    except Exception:
        session.rollback()
        raise
    return len(inserted_ids)


def persist_telemetry_batch(session: Session, raw_events: list[Any]) -> tuple[int, int, int]:
    """Validate each raw item, collect accepted rows, bulk-insert once.

    received is the raw list length. stored is rows actually inserted.
    rejected is received minus stored, covering validation failures, timestamp
    conversion failures, same-batch duplicate ids, and already-stored ids.
    """
    received = len(raw_events)
    accepted_rows: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()

    for raw_event in raw_events:
        try:
            event = TelemetryEvent.model_validate(raw_event)
        except ValidationError:
            continue
        try:
            timestamp = parse_event_timestamp(event.timestamp)
        except (TypeError, ValueError, OverflowError, OSError):
            continue
        if event.eventId in seen_event_ids:
            continue
        seen_event_ids.add(event.eventId)
        accepted_rows.append(
            {
                "event_id": event.eventId,
                "timestamp": timestamp,
                "session_id": event.sessionId,
                "user_id": event.userId,
                "event_type": event.event_type,
                "schema_version": event.schemaVersion,
                "request_id": event.requestId,
                "tags": project_tags(event.event_type, event.properties),
            }
        )

    stored = bulk_insert_telemetry_events(session, accepted_rows)
    rejected = received - stored
    return received, stored, rejected
