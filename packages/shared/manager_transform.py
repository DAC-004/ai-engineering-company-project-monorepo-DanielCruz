"""CSV row -> Incident Manager field transforms and derived seed markers.

The analyzer CSV schema is not the manager model. Valid rows must be mapped
before insert. CSV incident_id is used only to compute a digest; it is never
returned as a stored field value.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from manager_constants import (
    CSV_CATEGORY_MAP,
    CSV_CLINIC_TO_BRANCH,
    CSV_STATUS_MAP,
    DEFAULT_BRANCH,
    SEED_ORIGIN,
)


class TransformError(ValueError):
    """Raised when a CSV row cannot be mapped to manager fields."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(message)


def _cell(row: dict[str, Any], field: str) -> str:
    raw = row.get(field, "")
    if raw is None:
        return ""
    return str(raw).strip()


def title_from_description(description: str) -> str:
    """First 120 characters of description, trimmed. Empty result is invalid."""
    title = description[:120].strip()
    if not title:
        raise TransformError(
            "title",
            "Title is empty after taking the first 120 characters of the description.",
        )
    return title


def parse_created_at(date_text: str) -> datetime:
    """Parse YYYY-MM-DD as midnight UTC."""
    try:
        return datetime.strptime(date_text.strip(), "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as exc:
        raise TransformError(
            "created_at",
            "Date must be a valid YYYY-MM-DD value.",
        ) from exc


def map_status(csv_status: str) -> str:
    mapped = CSV_STATUS_MAP.get(csv_status.strip())
    if mapped is None:
        raise TransformError("status", "CSV status could not be mapped to a manager status.")
    return mapped


def map_category(csv_category: str) -> str:
    mapped = CSV_CATEGORY_MAP.get(csv_category.strip())
    if mapped is None:
        raise TransformError(
            "category",
            "CSV category could not be mapped to a manager category.",
        )
    return mapped


def map_branch(clinic_id: str) -> str:
    """Map clinic_id to a manager branch. Missing or unmapped codes use central."""
    cleaned = clinic_id.strip()
    if not cleaned:
        return DEFAULT_BRANCH
    return CSV_CLINIC_TO_BRANCH.get(cleaned, DEFAULT_BRANCH)


def derived_seed_marker(
    *,
    csv_incident_id: str,
    title: str,
    created_at: datetime,
) -> str:
    """SHA-256 digest for idempotency. Never returns the raw CSV incident_id.

    CONTEXT uses incident_id for duplicate control when present, otherwise
    title + created_at. Only the digest is suitable for persistence.
    """
    source = csv_incident_id.strip()
    if source:
        material = source.encode("utf-8")
    else:
        material = f"{title}|{created_at.isoformat()}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def transform_valid_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    """Map a validation-passing CSV row to manager fields plus a seed marker.

    Description is stored as the stripped cell text (not rewritten). Title is
    derived. origin is always customer. updated_at equals created_at on insert.
    """
    raw_description = row.get("description")
    description = "" if raw_description is None else str(raw_description)
    title = title_from_description(description)
    created_at = parse_created_at(_cell(row, "date"))
    marker = derived_seed_marker(
        csv_incident_id=_cell(row, "incident_id"),
        title=title,
        created_at=created_at,
    )
    return {
        "title": title,
        "description": description,
        "category": map_category(_cell(row, "category")),
        "status": map_status(_cell(row, "status")),
        "origin": SEED_ORIGIN,
        "branch": map_branch(_cell(row, "clinic_id")),
        "created_at": created_at,
        "updated_at": created_at,
        "marker": marker,
    }
