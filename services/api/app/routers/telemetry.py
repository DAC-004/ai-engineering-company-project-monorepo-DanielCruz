"""Telemetry ingest endpoint. Same URL as the capture stub; persistence is real.

The outer envelope is parsed loosely so one invalid event cannot HTTP 422 the
batch. Each item is validated with unchanged TelemetryEvent.model_validate.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.schemas.telemetry import TelemetryIngestResponse
from app.services.telemetry_storage import persist_telemetry_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def _parse_events_envelope(raw_body: bytes) -> list[Any]:
    """Parse JSON from application/json or sendBeacon text/plain bodies.

    HTTP 422 is preserved for empty bodies, invalid JSON, a missing events
    field, or a non-list events value. A parseable events list returns 200
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
    """Accept `{ "events": [...] }`, persist valid rows in one INSERT, return counts."""
    # Read the configured destination so the env pattern stays established. Do not log the value.
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
    return TelemetryIngestResponse(received=received, stored=stored, rejected=rejected)
