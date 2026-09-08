"""Pure transformation for Monthly Clinic Supply Performance KPIs.

Reads extracted v1 events (already projected off ``user_id``) and produces
clinic-month aggregates. This module never touches ``telemetry_events``.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

V1_EVENT_TYPES = frozenset(
    {
        "inbound_order_created",
        "outbound_order_created",
        "stock_threshold_triggered",
        "supply_expiry_flagged",
    }
)

CLINIC_ID_MIN = 1
CLINIC_ID_MAX = 12


def country_from_clinic_id(clinic_id: int) -> str | None:
    """Live clinic registry: 1-9 US, 10-12 UK. Same rule as countryFromClinicId."""
    if CLINIC_ID_MIN <= clinic_id <= 9:
        return "US"
    if 10 <= clinic_id <= CLINIC_ID_MAX:
        return "UK"
    return None


def currency_from_country(country: str) -> str | None:
    if country == "US":
        return "USD"
    if country == "UK":
        return "GBP"
    return None


def previous_completed_utc_month(now: datetime | None = None) -> date:
    """First day of the previous completed UTC calendar month."""
    current = now or datetime.now(UTC)
    first_of_this_month = date(current.year, current.month, 1)
    last_of_previous = first_of_this_month - timedelta(days=1)
    return date(last_of_previous.year, last_of_previous.month, 1)


def month_window(month_start: date) -> tuple[datetime, datetime]:
    """Inclusive UTC start and exclusive UTC end for one calendar month."""
    start = datetime(month_start.year, month_start.month, 1, tzinfo=UTC)
    if month_start.month == 12:
        end = datetime(month_start.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(month_start.year, month_start.month + 1, 1, tzinfo=UTC)
    return start, end


def coerce_clinic_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _is_finite_non_negative_cost(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value >= 0
    if isinstance(value, float):
        return math.isfinite(value) and value >= 0
    if isinstance(value, Decimal):
        return value.is_finite() and value >= 0
    return False


def _cost_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _event_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_tags(raw_tags: Any) -> dict[str, Any]:
    if raw_tags is None:
        return {}
    if isinstance(raw_tags, dict):
        return raw_tags
    if isinstance(raw_tags, str):
        import json

        stripped = raw_tags.strip()
        if not stripped:
            return {}
        loaded = json.loads(stripped)
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _empty_clinic_row(clinic_id: int, month_start: date) -> dict[str, Any]:
    country = country_from_clinic_id(clinic_id)
    assert country is not None
    currency = currency_from_country(country)
    assert currency is not None
    return {
        "clinic_id": str(clinic_id),
        "country": country,
        "month_start": month_start,
        "total_supply_cost": Decimal("0"),
        "supply_consumption_count": 0,
        "critical_stockout_count": 0,
        "expiry_risk_count": 0,
        "currency": currency,
    }


def transform_monthly_clinic_aggregates(
    events: list[dict[str, Any]],
    month_start: date,
) -> dict[str, Any]:
    """Convert extracted v1 events into clinic-month KPI rows.

    Invalid rows are dropped from aggregates and counted in ``records_rejected``.
    Duplicate ``event_id`` values keep the first occurrence. Duplicate inbound or
    outbound business keys keep the earliest ``timestamp`` (source has no
    ``ingested_at`` column). Department on outbound events is ignored: the
    destination grain is clinic-month, not department-month.
    """
    records_extracted = len(events)
    records_rejected = 0
    seen_event_ids: set[str] = set()
    inbound_keys: dict[int, datetime] = {}
    outbound_keys: dict[int, datetime] = {}
    surviving: list[dict[str, Any]] = []
    max_event_timestamp: datetime | None = None

    window_start, window_end = month_window(month_start)

    for raw_event in events:
        event_id = raw_event.get("event_id")
        event_type = raw_event.get("event_type")
        occurred_at = _event_timestamp(raw_event.get("timestamp"))
        tags = _parse_tags(raw_event.get("tags"))

        if not isinstance(event_id, str) or not event_id:
            records_rejected += 1
            continue
        if event_id in seen_event_ids:
            records_rejected += 1
            continue
        seen_event_ids.add(event_id)

        if event_type not in V1_EVENT_TYPES:
            records_rejected += 1
            continue
        if occurred_at is None or occurred_at < window_start or occurred_at >= window_end:
            records_rejected += 1
            continue

        clinic_id = coerce_clinic_id(tags.get("clinic_id"))
        country = tags.get("country")
        expected_country = country_from_clinic_id(clinic_id) if clinic_id is not None else None
        if (
            clinic_id is None
            or expected_country is None
            or country not in ("US", "UK")
            or country != expected_country
        ):
            records_rejected += 1
            continue

        if event_type == "inbound_order_created":
            inbound_order_id = tags.get("inbound_order_id")
            if not isinstance(inbound_order_id, int) or isinstance(inbound_order_id, bool):
                records_rejected += 1
                continue
            previous_ts = inbound_keys.get(inbound_order_id)
            if previous_ts is not None:
                records_rejected += 1
                continue
            inbound_keys[inbound_order_id] = occurred_at
            if not _is_finite_non_negative_cost(tags.get("total_cost")):
                records_rejected += 1
                continue

        if event_type == "outbound_order_created":
            outbound_order_id = tags.get("outbound_order_id")
            if not isinstance(outbound_order_id, int) or isinstance(outbound_order_id, bool):
                records_rejected += 1
                continue
            if outbound_order_id in outbound_keys:
                records_rejected += 1
                continue
            outbound_keys[outbound_order_id] = occurred_at

        surviving.append(
            {
                "event_id": event_id,
                "event_type": event_type,
                "timestamp": occurred_at,
                "clinic_id": clinic_id,
                "country": country,
                "tags": tags,
            }
        )
        if max_event_timestamp is None or occurred_at > max_event_timestamp:
            max_event_timestamp = occurred_at

    grouped: dict[str, dict[str, Any]] = {}
    for event in surviving:
        clinic_key = str(event["clinic_id"])
        row = grouped.get(clinic_key)
        if row is None:
            row = _empty_clinic_row(event["clinic_id"], month_start)
            grouped[clinic_key] = row
        if row["country"] != event["country"] or row["currency"] != currency_from_country(
            event["country"]
        ):
            raise ValueError(
                f"Mixed country or currency for clinic_id={clinic_key} month_start={month_start.isoformat()}"
            )
        event_type = event["event_type"]
        if event_type == "inbound_order_created":
            row["total_supply_cost"] += _cost_decimal(event["tags"]["total_cost"])
        elif event_type == "outbound_order_created":
            row["supply_consumption_count"] += 1
        elif event_type == "stock_threshold_triggered":
            row["critical_stockout_count"] += 1
        elif event_type == "supply_expiry_flagged":
            row["expiry_risk_count"] += 1

    aggregates = [grouped[key] for key in sorted(grouped, key=lambda item: int(item))]
    return {
        "aggregates": aggregates,
        "records_extracted": records_extracted,
        "records_rejected": records_rejected,
        "month_start": month_start,
        "max_event_timestamp": max_event_timestamp,
    }


def fill_zero_clinic_rows(
    aggregates: list[dict[str, Any]],
    month_start: date,
) -> list[dict[str, Any]]:
    """Ensure all 12 clinics appear after a successful Completed run."""
    by_clinic = {row["clinic_id"]: row for row in aggregates}
    filled: list[dict[str, Any]] = []
    for clinic_id in range(CLINIC_ID_MIN, CLINIC_ID_MAX + 1):
        clinic_key = str(clinic_id)
        filled.append(by_clinic.get(clinic_key, _empty_clinic_row(clinic_id, month_start)))
    return filled
