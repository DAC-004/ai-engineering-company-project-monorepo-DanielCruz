"""TinyDB CRUD and lifecycle rules for HealthCore incidents."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from tinydb import Query

from manager_constants import (
    ALLOWED_TRANSITIONS,
    BRANCHES,
    CATEGORIES,
    ORIGINS,
    STATUSES,
)

from app.db.tinydb import incident_seed_keys_table, incidents_table
from app.schemas.incident import IncidentCreate, IncidentInDB, IncidentSummary


class IncidentFieldError(ValueError):
    """Assignment-defined field validation failure (HTTP 400)."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(message)


class IncidentNotFoundError(LookupError):
    """Raised when an incident id is not in the store (HTTP 404)."""


def _row_to_incident(row: dict) -> IncidentInDB:
    return IncidentInDB.model_validate(row)


def _require_non_empty(field: str, value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise IncidentFieldError(field, f"{label} is required.")
    return cleaned


def _require_allowed(field: str, value: str, allowed: tuple[str, ...], label: str) -> str:
    cleaned = _require_non_empty(field, value, label)
    if cleaned not in allowed:
        allowed_list = ", ".join(allowed)
        raise IncidentFieldError(
            field,
            f"{label} must be one of: {allowed_list}.",
        )
    return cleaned


def validate_create_payload(payload: IncidentCreate) -> dict[str, str]:
    """Validate operator create fields against HealthCore allowed values."""
    return {
        "title": _require_non_empty("title", payload.title, "Title"),
        "description": _require_non_empty("description", payload.description, "Description"),
        "category": _require_allowed("category", payload.category, CATEGORIES, "Category"),
        "status": _require_allowed("status", payload.status, STATUSES, "Status"),
        "origin": _require_allowed("origin", payload.origin, ORIGINS, "Origin"),
        "branch": _require_allowed("branch", payload.branch, BRANCHES, "Branch"),
    }


def create_incident(payload: IncidentCreate) -> IncidentInDB:
    fields = validate_create_payload(payload)
    now = datetime.now(UTC)
    incident = IncidentInDB(
        id=str(uuid4()),
        created_at=now,
        updated_at=now,
        **fields,
    )
    incidents_table().insert(incident.model_dump(mode="json"))
    return incident


def insert_historical_incident(fields: dict) -> IncidentInDB | None:
    """Insert a transformed seed row if its derived marker is new.

    `fields` must include manager model values plus `marker` (SHA-256 digest).
    Returns None when the marker already exists so re-runs do not duplicate.
    """
    marker = fields["marker"]
    keys = incident_seed_keys_table()
    if keys.get(Query().marker == marker):
        return None

    incident = IncidentInDB(
        id=str(uuid4()),
        title=fields["title"],
        description=fields["description"],
        category=fields["category"],
        status=fields["status"],
        origin=fields["origin"],
        branch=fields["branch"],
        created_at=fields["created_at"],
        updated_at=fields["updated_at"],
    )
    incidents_table().insert(incident.model_dump(mode="json"))
    # Store only the digest and the generated model UUID — never the CSV id.
    keys.insert({"marker": marker, "incident_id": incident.id})
    return incident


def get_incident(incident_id: str) -> IncidentInDB:
    row = incidents_table().get(Query().id == incident_id)
    if row is None:
        raise IncidentNotFoundError(incident_id)
    return _row_to_incident(row)


def list_incidents(
    *,
    status: str | None = None,
    origin: str | None = None,
    branch: str | None = None,
    category: str | None = None,
) -> list[IncidentInDB]:
    """Return incidents matching optional exact filters. Empty store is []."""
    filters = {
        "status": status,
        "origin": origin,
        "branch": branch,
        "category": category,
    }
    allowed = {
        "status": STATUSES,
        "origin": ORIGINS,
        "branch": BRANCHES,
        "category": CATEGORIES,
    }
    query_parts = []
    Incident = Query()
    for field, value in filters.items():
        if value is None or value == "":
            continue
        cleaned = value.strip()
        if cleaned not in allowed[field]:
            label = field.replace("_", " ").title()
            raise IncidentFieldError(
                field,
                f"{label} must be one of: {', '.join(allowed[field])}.",
            )
        query_parts.append(getattr(Incident, field) == cleaned)

    table = incidents_table()
    if not query_parts:
        rows = table.all()
    else:
        combined = query_parts[0]
        for part in query_parts[1:]:
            combined = combined & part
        rows = table.search(combined)
    return [_row_to_incident(row) for row in rows]


def update_incident_status(incident_id: str, new_status: str) -> IncidentInDB:
    """Apply an allowed lifecycle transition and advance updated_at only."""
    cleaned = _require_allowed("status", new_status, STATUSES, "Status")
    existing = get_incident(incident_id)
    permitted = ALLOWED_TRANSITIONS[existing.status]
    if cleaned not in permitted:
        if not permitted:
            raise IncidentFieldError(
                "status",
                f"A {existing.status} incident is final and cannot change status.",
            )
        allowed_list = ", ".join(sorted(permitted))
        raise IncidentFieldError(
            "status",
            f"An {existing.status} incident can only move to: {allowed_list}.",
        )

    now = datetime.now(UTC)
    incidents_table().update(
        {
            "status": cleaned,
            "updated_at": now.isoformat(),
        },
        Query().id == incident_id,
    )
    return get_incident(incident_id)


def summarize_incidents() -> IncidentSummary:
    """Zero-filled totals for every allowed HealthCore value, even if empty."""
    summary = IncidentSummary(
        by_status={status: 0 for status in STATUSES},
        by_category={category: 0 for category in CATEGORIES},
        by_origin={origin: 0 for origin in ORIGINS},
        by_branch={branch: 0 for branch in BRANCHES},
    )
    for incident in list_incidents():
        if incident.status in summary.by_status:
            summary.by_status[incident.status] += 1
        if incident.category in summary.by_category:
            summary.by_category[incident.category] += 1
        if incident.origin in summary.by_origin:
            summary.by_origin[incident.origin] += 1
        if incident.branch in summary.by_branch:
            summary.by_branch[incident.branch] += 1
    return summary
