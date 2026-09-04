"""Persistent telemetry ingestion plus the operational report endpoint.

POST /telemetry/events validates each event independently and persists accepted
rows. GET /telemetry/report reads the stored ``telemetry_events`` table through
the separate technical analysis pipeline.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from app.core.config import get_settings
from app.db.database import get_db, get_engine
from app.schemas.telemetry import TelemetryIngestResponse, TelemetryReportResponse
from app.services.telemetry_storage import persist_telemetry_batch


# Repo root is required so ``services.telemetry.analysis`` is importable when
# uvicorn is started from services/api.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.telemetry import analysis as telemetry_analysis  # noqa: E402


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

REPORT_CACHE_TTL_SECONDS = 60
_report_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_report_cache_lock = Lock()


def clear_telemetry_report_cache() -> None:
    """Drop every cached report. Used by validation so cases stay independent."""

    with _report_cache_lock:
        _report_cache.clear()


def _parse_report_bound(raw: str | None, *, field_name: str) -> datetime | None:
    """Parse an optional ISO 8601 query value as a UTC-aware datetime."""

    if raw is None or raw.strip() == "":
        return None
    try:
        parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be an ISO 8601 datetime",
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _aligned_utc_now(ttl_seconds: int = REPORT_CACHE_TTL_SECONDS) -> datetime:
    """Floor UTC now to the cache TTL so omitted-parameter requests share a window.

    ``datetime.now()`` changes every request. Without alignment, the default
    seven-day window would miss the cache on every call even though the caller
    asked for the same implicit period.
    """

    now = datetime.now(UTC)
    epoch_seconds = int(now.timestamp())
    aligned_epoch = epoch_seconds - (epoch_seconds % ttl_seconds)
    return datetime.fromtimestamp(aligned_epoch, tz=UTC)


def _resolve_report_period(
    start_date: str | None,
    end_date: str | None,
) -> tuple[datetime, datetime]:
    """Resolve omitted bounds to the last seven UTC days and reject inverted windows."""

    parsed_start = _parse_report_bound(start_date, field_name="start_date")
    parsed_end = _parse_report_bound(end_date, field_name="end_date")
    aligned_now = _aligned_utc_now()
    resolved_end = parsed_end or aligned_now
    resolved_start = parsed_start or (aligned_now - timedelta(days=7))
    if resolved_start >= resolved_end:
        raise HTTPException(
            status_code=422,
            detail="start_date must be earlier than end_date",
        )
    return resolved_start, resolved_end


def _isoformat_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _report_cache_key(start_date: datetime, end_date: datetime) -> tuple[str, str]:
    """Return a stable UTC key so equivalent ISO inputs share one cache entry."""

    return (_isoformat_utc(start_date), _isoformat_utc(end_date))


def _cached_telemetry_report(
    start_date: datetime,
    end_date: datetime,
) -> dict[str, Any]:
    """Return the report for this exact window, recomputing on miss or expiry."""

    cache_key = _report_cache_key(start_date, end_date)
    now_monotonic = time.monotonic()
    with _report_cache_lock:
        cached = _report_cache.get(cache_key)
        if cached is not None and cached[0] > now_monotonic:
            return cached[1]

    report = telemetry_analysis.build_telemetry_report(
        start_date,
        end_date,
        engine=get_engine(),
    )

    with _report_cache_lock:
        _report_cache[cache_key] = (
            time.monotonic() + REPORT_CACHE_TTL_SECONDS,
            report,
        )
    return report


def _parse_events_envelope(raw_body: bytes) -> list[Any]:
    """Parse JSON from application/json or sendBeacon text/plain bodies.

    HTTP 422 is preserved for empty bodies, invalid JSON, a missing events
    field, or a non-list events value. A parseable events list returns HTTP 200
    even when every item is later rejected.
    """

    if not raw_body:
        raise HTTPException(
            status_code=422,
            detail="Request body is required",
        )
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Body must be JSON",
        ) from exc
    if not isinstance(payload, dict) or "events" not in payload:
        raise HTTPException(
            status_code=422,
            detail="Body must contain an events list",
        )
    raw_events = payload["events"]
    if not isinstance(raw_events, list):
        raise HTTPException(
            status_code=422,
            detail="events must be a list",
        )
    return raw_events


@router.post("/events", response_model=TelemetryIngestResponse)
async def ingest_telemetry_events(
    request: Request,
    session: Session = Depends(get_db),
) -> TelemetryIngestResponse:
    """Accept an events list, persist valid rows once, and return batch counts."""

    # Read the configured destination so the environment pattern stays
    # established. Do not log the configured value.
    get_settings().telemetry_endpoint
    logger.debug("Telemetry endpoint configuration was read")

    raw_events = _parse_events_envelope(await request.body())
    received, stored, rejected = persist_telemetry_batch(session, raw_events)

    logger.info(
        "Telemetry batch received=%s stored=%s rejected=%s",
        received,
        stored,
        rejected,
    )
    return TelemetryIngestResponse(
        received=received,
        stored=stored,
        rejected=rejected,
    )


@router.get("/report", response_model=TelemetryReportResponse)
def get_telemetry_report(
    start_date: str | None = Query(
        default=None,
        description="Inclusive ISO 8601 UTC start",
    ),
    end_date: str | None = Query(
        default=None,
        description="Exclusive ISO 8601 UTC end",
    ),
) -> dict[str, Any]:
    """Serve cached operational metrics for one resolved UTC window."""

    resolved_start, resolved_end = _resolve_report_period(start_date, end_date)
    return _cached_telemetry_report(resolved_start, resolved_end)
