"""Centralized Incident Manager endpoints (create, list, detail, status, summary)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.access.permissions import (
    assert_department_allowed,
    filter_department_rows,
    require_authenticated,
    require_create_record,
    require_update_record,
)
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
    current_user: UserInDB = Depends(require_create_record),
) -> IncidentPublic:
    """Create an incident. Generated id and timestamps are assigned by the service."""
    # Own-department create: a missing caller department is not a match.
    assert_department_allowed(current_user, current_user.department_id)
    return incident_service.create_incident(
        payload,
        department_id=current_user.department_id,
    )


@router.get("", response_model=list[IncidentPublic])
def list_incidents(
    status: str | None = Query(default=None),
    origin: str | None = Query(default=None),
    branch: str | None = Query(default=None),
    category: str | None = Query(default=None),
    current_user: UserInDB = Depends(require_authenticated),
) -> list[IncidentPublic]:
    """Return incidents. Optional filters are exact HealthCore model values."""
    rows = incident_service.list_incidents(
        status=status,
        origin=origin,
        branch=branch,
        category=category,
    )
    return filter_department_rows(current_user, rows, lambda row: row.department_id)


@router.get("/summary", response_model=IncidentSummary)
def incident_summary(
    current_user: UserInDB = Depends(require_authenticated),
) -> IncidentSummary:
    """Aggregate totals by status, category, origin, and branch for visible incidents."""
    visible = filter_department_rows(
        current_user,
        incident_service.list_incidents(),
        lambda row: row.department_id,
    )
    return incident_service.summarize_incidents_from(visible)


@router.get("/{incident_id}", response_model=IncidentPublic)
def get_incident(
    incident_id: str,
    current_user: UserInDB = Depends(require_authenticated),
) -> IncidentPublic:
    incident = incident_service.get_incident(incident_id)
    assert_department_allowed(current_user, incident.department_id)
    return incident


@router.patch("/{incident_id}/status", response_model=IncidentPublic)
def patch_incident_status(
    incident_id: str,
    payload: IncidentStatusUpdate,
    current_user: UserInDB = Depends(require_update_record),
) -> IncidentPublic:
    """Update status only. Enforces the HealthCore lifecycle. Advances updated_at."""
    incident = incident_service.get_incident(incident_id)
    assert_department_allowed(current_user, incident.department_id)
    return incident_service.update_incident_status(incident_id, payload.status)
