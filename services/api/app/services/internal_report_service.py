"""TinyDB persistence for the canonical department-scoped internal-reports collection."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from tinydb import Query

from app.db.tinydb import internal_reports_table
from app.schemas.internal_report import InternalReportPublic, InternalReportUpdate


class InternalReportNotFoundError(LookupError):
    pass


def _row(row: dict) -> InternalReportPublic:
    return InternalReportPublic.model_validate(row)


def create_report(
    *,
    department_id: str,
    title: str,
    body: str,
    created_by: str,
) -> InternalReportPublic:
    record = InternalReportPublic(
        id=str(uuid4()),
        department_id=department_id,
        title=title,
        body=body,
        created_by=created_by,
        created_at=datetime.now(UTC),
    )
    internal_reports_table().insert(record.model_dump(mode="json"))
    return record


def list_reports() -> list[InternalReportPublic]:
    return [_row(row) for row in internal_reports_table().all()]


def get_report(report_id: str) -> InternalReportPublic:
    row = internal_reports_table().get(Query().id == report_id)
    if row is None:
        raise InternalReportNotFoundError(report_id)
    return _row(row)


def update_report(report_id: str, payload: InternalReportUpdate) -> InternalReportPublic:
    table = internal_reports_table()
    existing = table.get(Query().id == report_id)
    if existing is None:
        raise InternalReportNotFoundError(report_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates:
        table.update(updates, Query().id == report_id)
    refreshed = table.get(Query().id == report_id)
    return _row(refreshed)


def delete_report(report_id: str) -> None:
    removed = internal_reports_table().remove(Query().id == report_id)
    if not removed:
        raise InternalReportNotFoundError(report_id)
