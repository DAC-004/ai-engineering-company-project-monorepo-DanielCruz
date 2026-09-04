"""Pydantic envelope for HealthCore telemetry batches.

Matches docs/telemetry/telemetry-plan.md section 6.0 and event-schemas.json.
TelemetryEvent is the unchanged capture-phase envelope contract. Storage
projects allowlisted properties into tags after per-event model_validate.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TelemetryEvent(BaseModel):
    """Standard capture envelope. Extra root keys are rejected."""

    model_config = ConfigDict(extra="forbid")

    eventId: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    sessionId: str = Field(min_length=1)
    userId: str | None
    event_type: str = Field(min_length=1)
    schemaVersion: str = Field(min_length=1)
    requestId: str = Field(min_length=1)
    properties: dict[str, Any]


class TelemetryBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[TelemetryEvent]


class TelemetryIngestResponse(BaseModel):
    received: int
    stored: int
    rejected: int
