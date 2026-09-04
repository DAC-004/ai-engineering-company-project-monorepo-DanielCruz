"""Isolated unit tests for Monthly Clinic Supply Performance KPI transforms.

Fixtures are in-memory HealthCore telemetry_events shapes (timestamp + tags).
These tests do not open a database or call Supabase or any external API.
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.transforms import transform_monthly_clinic_aggregates

JULY_2026 = date(2026, 7, 1)


def _event(
    *,
    event_id: str,
    event_type: str,
    timestamp: str,
    clinic_id: int,
    country: str,
    extra_tags: dict | None = None,
) -> dict:
    """Shape extracted HealthCore v1 events after user_id is projected out."""
    tags = {"clinic_id": clinic_id, "country": country}
    if extra_tags:
        tags.update(extra_tags)
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "tags": tags,
    }


def _clinic_row(result: dict, clinic_id: str) -> dict | None:
    for row in result["aggregates"]:
        if row["clinic_id"] == clinic_id:
            return row
    return None


def test_supply_cost_per_clinic_sums_inbound_order_total_cost() -> None:
    """Supply Cost per Clinic is the sum of inbound tags.total_cost for the month.

    Hand-calculated: clinic 3 (US) has 120.40 + 30.10 = 150.50 USD.
    Clinic 11 (UK) has a single inbound of 80.00 GBP. USD and GBP stay separate.
    """
    events = [
        _event(
            event_id="in-us-1",
            event_type="inbound_order_created",
            timestamp="2026-07-03T10:00:00+00:00",
            clinic_id=3,
            country="US",
            extra_tags={"inbound_order_id": 11, "total_cost": 120.40},
        ),
        _event(
            event_id="in-us-2",
            event_type="inbound_order_created",
            timestamp="2026-07-18T15:30:00+00:00",
            clinic_id=3,
            country="US",
            extra_tags={"inbound_order_id": 12, "total_cost": 30.10},
        ),
        _event(
            event_id="in-uk-1",
            event_type="inbound_order_created",
            timestamp="2026-07-08T09:00:00+00:00",
            clinic_id=11,
            country="UK",
            extra_tags={"inbound_order_id": 21, "total_cost": 80.00},
        ),
    ]

    result = transform_monthly_clinic_aggregates(events, JULY_2026)
    us_row = _clinic_row(result, "3")
    uk_row = _clinic_row(result, "11")

    assert us_row is not None
    assert uk_row is not None
    assert us_row["country"] == "US"
    assert us_row["currency"] == "USD"
    assert us_row["total_supply_cost"] == Decimal("150.50")
    assert uk_row["country"] == "UK"
    assert uk_row["currency"] == "GBP"
    assert uk_row["total_supply_cost"] == Decimal("80.00")
    assert us_row["total_supply_cost"] + uk_row["total_supply_cost"] != us_row["total_supply_cost"]


def test_supply_consumption_volume_counts_outbound_order_created_events() -> None:
    """Supply Consumption Volume is a clinic-month count of outbound_order_created.

    Destination grain has no department column. Department on the source event
    is ignored; three outbound events at clinic 5 still equal 3.
    """
    events = [
        _event(
            event_id="out-1",
            event_type="outbound_order_created",
            timestamp="2026-07-02T08:00:00+00:00",
            clinic_id=5,
            country="US",
            extra_tags={
                "outbound_order_id": 31,
                "department": "primary_care",
            },
        ),
        _event(
            event_id="out-2",
            event_type="outbound_order_created",
            timestamp="2026-07-09T11:00:00+00:00",
            clinic_id=5,
            country="US",
            extra_tags={
                "outbound_order_id": 32,
                "department": "specialty_care",
            },
        ),
        _event(
            event_id="out-3",
            event_type="outbound_order_created",
            timestamp="2026-07-22T16:00:00+00:00",
            clinic_id=5,
            country="US",
            extra_tags={
                "outbound_order_id": 33,
                "department": "chronic_care",
            },
        ),
    ]

    result = transform_monthly_clinic_aggregates(events, JULY_2026)
    row = _clinic_row(result, "5")

    assert row is not None
    assert row["supply_consumption_count"] == 3
    assert row["total_supply_cost"] == Decimal("0")
    assert "department" not in row


def test_critical_stockout_frequency_counts_stock_threshold_triggered_events() -> None:
    """Critical Stockout Frequency is the count of stock_threshold_triggered events."""
    events = [
        _event(
            event_id="stockout-1",
            event_type="stock_threshold_triggered",
            timestamp="2026-07-04T12:00:00+00:00",
            clinic_id=8,
            country="US",
            extra_tags={"product_id": 4, "triggering_outbound_order_id": 40},
        ),
        _event(
            event_id="stockout-2",
            event_type="stock_threshold_triggered",
            timestamp="2026-07-19T12:00:00+00:00",
            clinic_id=8,
            country="US",
            extra_tags={"product_id": 7, "triggering_outbound_order_id": 41},
        ),
        _event(
            event_id="expiry-other-clinic",
            event_type="supply_expiry_flagged",
            timestamp="2026-07-19T13:00:00+00:00",
            clinic_id=10,
            country="UK",
            extra_tags={"product_id": 7},
        ),
    ]

    result = transform_monthly_clinic_aggregates(events, JULY_2026)
    us_row = _clinic_row(result, "8")
    uk_row = _clinic_row(result, "10")

    assert us_row is not None
    assert us_row["critical_stockout_count"] == 2
    assert us_row["expiry_risk_count"] == 0
    assert uk_row is not None
    assert uk_row["expiry_risk_count"] == 1
    assert uk_row["critical_stockout_count"] == 0


def test_expiry_risk_count_counts_supply_expiry_flagged_events() -> None:
    """Expiry Risk Count is the count of supply_expiry_flagged events in the month."""
    events = [
        _event(
            event_id="expiry-1",
            event_type="supply_expiry_flagged",
            timestamp="2026-07-01T00:30:00+00:00",
            clinic_id=12,
            country="UK",
            extra_tags={"product_id": 2},
        ),
        _event(
            event_id="expiry-2",
            event_type="supply_expiry_flagged",
            timestamp="2026-07-31T23:00:00+00:00",
            clinic_id=12,
            country="UK",
            extra_tags={"product_id": 9},
        ),
    ]

    result = transform_monthly_clinic_aggregates(events, JULY_2026)
    row = _clinic_row(result, "12")

    assert row is not None
    assert row["expiry_risk_count"] == 2
    assert row["currency"] == "GBP"


def test_inbound_order_created_without_total_cost_is_rejected() -> None:
    """Missing or malformed inbound total_cost is excluded from Supply Cost per Clinic."""
    events = [
        _event(
            event_id="valid-cost",
            event_type="inbound_order_created",
            timestamp="2026-07-05T10:00:00+00:00",
            clinic_id=1,
            country="US",
            extra_tags={"inbound_order_id": 50, "total_cost": 40.00},
        ),
        _event(
            event_id="missing-cost",
            event_type="inbound_order_created",
            timestamp="2026-07-06T10:00:00+00:00",
            clinic_id=1,
            country="US",
            extra_tags={"inbound_order_id": 51},
        ),
        _event(
            event_id="negative-cost",
            event_type="inbound_order_created",
            timestamp="2026-07-07T10:00:00+00:00",
            clinic_id=1,
            country="US",
            extra_tags={"inbound_order_id": 52, "total_cost": -5},
        ),
        _event(
            event_id="null-cost",
            event_type="inbound_order_created",
            timestamp="2026-07-08T10:00:00+00:00",
            clinic_id=1,
            country="US",
            extra_tags={"inbound_order_id": 53, "total_cost": None},
        ),
        {
            "event_id": "wrong-type-cost",
            "timestamp": "2026-07-09T10:00:00+00:00",
            "event_type": "inbound_order_created",
            "tags": {
                "clinic_id": 1,
                "country": "US",
                "inbound_order_id": 54,
                "total_cost": "not-a-number",
            },
        },
    ]

    result = transform_monthly_clinic_aggregates(events, JULY_2026)
    row = _clinic_row(result, "1")

    assert result["records_extracted"] == 5
    assert result["records_rejected"] == 4
    assert row is not None
    assert row["total_supply_cost"] == Decimal("40.00")


def test_malformed_clinic_identity_is_rejected_from_kpi_aggregates() -> None:
    """Invalid clinic_id, missing event_id, and out-of-month timestamps are dropped."""
    events = [
        {
            "event_id": "bad-clinic-slug",
            "timestamp": "2026-07-10T10:00:00+00:00",
            "event_type": "outbound_order_created",
            "tags": {
                "clinic_id": "austin-north",
                "country": "US",
                "outbound_order_id": 60,
            },
        },
        {
            "event_id": None,
            "timestamp": "2026-07-10T11:00:00+00:00",
            "event_type": "stock_threshold_triggered",
            "tags": {"clinic_id": 2, "country": "US", "product_id": 1},
        },
        _event(
            event_id="wrong-month",
            event_type="supply_expiry_flagged",
            timestamp="2026-08-01T00:00:00+00:00",
            clinic_id=2,
            country="US",
            extra_tags={"product_id": 1},
        ),
        _event(
            event_id="country-mismatch",
            event_type="outbound_order_created",
            timestamp="2026-07-10T12:00:00+00:00",
            clinic_id=2,
            country="UK",
            extra_tags={"outbound_order_id": 61},
        ),
        _event(
            event_id="valid-outbound",
            event_type="outbound_order_created",
            timestamp="2026-07-10T13:00:00+00:00",
            clinic_id=2,
            country="US",
            extra_tags={"outbound_order_id": 62},
        ),
    ]

    result = transform_monthly_clinic_aggregates(events, JULY_2026)
    row = _clinic_row(result, "2")

    assert result["records_extracted"] == 5
    assert result["records_rejected"] == 4
    assert row is not None
    assert row["supply_consumption_count"] == 1
    assert _clinic_row(result, "austin-north") is None
