"""Pydantic contracts for HealthCore telemetry ingestion and reporting.

The capture envelope matches docs/telemetry/telemetry-plan.md section 6.0 and
event-schemas.json. Storage projects allowlisted properties into tags after
per-event ``TelemetryEvent.model_validate``. The report models describe the
engineering-facing ``GET /telemetry/report`` response.
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
    """Strict request envelope used by telemetry capture clients."""

    model_config = ConfigDict(extra="forbid")

    events: list[TelemetryEvent]


class TelemetryIngestResponse(BaseModel):
    """Counts returned after validating and persisting one telemetry batch."""

    received: int
    stored: int
    rejected: int


class TelemetryReportPeriod(BaseModel):
    """Resolved UTC window passed to every technical metric function."""

    model_config = ConfigDict(extra="forbid")

    from_: str = Field(alias="from")
    to: str


class TelemetryReportResponse(BaseModel):
    """Grouped operational metrics returned by GET /telemetry/report."""

    model_config = ConfigDict(extra="forbid")

    period: TelemetryReportPeriod
    metrics: dict[str, list[dict[str, Any]]]
