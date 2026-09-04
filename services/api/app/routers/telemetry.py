"""Telemetry ingest stub plus the operational report endpoint.

POST /telemetry/events remains a validate-and-acknowledge receiver. Persistence
of capture batches is outside this module; GET /telemetry/report reads the
already-stored ``telemetry_events`` table through the analysis pipeline.
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

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import ValidationError

from app.core.config import get_settings
from app.db.database import get_engine
from app.schemas.telemetry import (
    TelemetryBatch,
    TelemetryEvent,
    TelemetryIngestResponse,
    TelemetryReportResponse,
)

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
    """Stable UTC key so equivalent ISO inputs share one cache entry."""
    return (_isoformat_utc(start_date), _isoformat_utc(end_date))


def _cached_telemetry_report(start_date: datetime, end_date: datetime) -> dict[str, Any]:
    """Return the report for this exact window, recomputing only on miss or expiry."""
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


def _parse_batch(raw_body: bytes) -> TelemetryBatch:
    """Parse JSON from application/json or sendBeacon text/plain bodies."""
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
    try:
        return TelemetryBatch.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(),
        ) from exc


@router.post("/events", response_model=TelemetryIngestResponse)
async def ingest_telemetry_events(request: Request) -> TelemetryIngestResponse:
    """
    Accept `{ "events": [TelemetryEvent, ...] }`, log counts, return received N.

    Reads TELEMETRY_ENDPOINT so the env pattern is established now, even though
    this stub does not redirect traffic.
    """
    _configured_endpoint = get_settings().telemetry_endpoint
    logger.debug("TELEMETRY_ENDPOINT=%s", _configured_endpoint)

    batch = _parse_batch(await request.body())
    events: list[TelemetryEvent] = batch.events

    logger.info("Received %s telemetry events", len(events))
    for event in events:
        logger.info("event_type=%s", event.event_type)

    return TelemetryIngestResponse(received=len(events))


@router.get("/report", response_model=TelemetryReportResponse)
def get_telemetry_report(
    start_date: str | None = Query(default=None, description="Inclusive ISO 8601 UTC start"),
    end_date: str | None = Query(default=None, description="Exclusive ISO 8601 UTC end"),
) -> dict[str, Any]:
    """Serve cached operational metrics for one resolved UTC window."""
    resolved_start, resolved_end = _resolve_report_period(start_date, end_date)
    return _cached_telemetry_report(resolved_start, resolved_end)
