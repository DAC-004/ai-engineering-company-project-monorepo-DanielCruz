"""Temporary telemetry receiver. Validates batches and returns HTTP 200.

No database writes. Persistence is Phase 3. The destination URL is declared
as TELEMETRY_ENDPOINT so later replacement of this stub does not change the
configuration pattern.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.telemetry import TelemetryBatch, TelemetryEvent, TelemetryIngestResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


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
