"""Centralized Incident Manager endpoints (create, list, detail, status, summary)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.deps import get_current_user
from app.schemas.incident import (
    IncidentCreate,
    IncidentPublic,
    IncidentStatusUpdate,
    IncidentSummary,
)
from app.schemas.user import UserInDB
from app.services import incident_service

router = APIRouter(prefix="/api/incidents", tags=["incident-manager"])


@router.post("", response_model=IncidentPublic)
def create_incident(
    payload: IncidentCreate,
    _current_user: UserInDB = Depends(get_current_user),
) -> IncidentPublic:
    """Create an incident. Generated id and timestamps are assigned by the service."""
    return incident_service.create_incident(payload)


@router.get("", response_model=list[IncidentPublic])
def list_incidents(
    status: str | None = Query(default=None),
    origin: str | None = Query(default=None),
    branch: str | None = Query(default=None),
    category: str | None = Query(default=None),
    _current_user: UserInDB = Depends(get_current_user),
) -> list[IncidentPublic]:
    """Return incidents. Optional filters are exact HealthCore model values."""
    return incident_service.list_incidents(
        status=status,
        origin=origin,
        branch=branch,
        category=category,
    )


@router.get("/summary", response_model=IncidentSummary)
def incident_summary(
    _current_user: UserInDB = Depends(get_current_user),
) -> IncidentSummary:
    """Aggregate totals by status, category, origin, and branch."""
    return incident_service.summarize_incidents()


@router.get("/{incident_id}", response_model=IncidentPublic)
def get_incident(
    incident_id: str,
    _current_user: UserInDB = Depends(get_current_user),
) -> IncidentPublic:
    return incident_service.get_incident(incident_id)


@router.patch("/{incident_id}/status", response_model=IncidentPublic)
def patch_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    _current_user: UserInDB = Depends(get_current_user),
) -> IncidentPublic:
    """Update status only. Enforces the HealthCore lifecycle. Advances updated_at."""
    return incident_service.update_incident_status(incident_id, payload.status)
