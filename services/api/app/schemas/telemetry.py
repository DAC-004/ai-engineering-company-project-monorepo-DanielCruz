"""Pydantic envelope for HealthCore telemetry batches.

Matches docs/telemetry/telemetry-plan.md section 6.0 and event-schemas.json.
This stub validates the envelope only. Per-event property allowlists are the
frontend/instrumenter contract and are not persisted here.
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


class TelemetryReportPeriod(BaseModel):
    """Resolved UTC window passed to every metric function."""

    model_config = ConfigDict(extra="forbid")

    from_: str = Field(alias="from")
    to: str


class TelemetryReportResponse(BaseModel):
    """Grouped operational metrics for GET /telemetry/report."""

    model_config = ConfigDict(extra="forbid")

    period: TelemetryReportPeriod
    metrics: dict[str, list[dict[str, Any]]]
