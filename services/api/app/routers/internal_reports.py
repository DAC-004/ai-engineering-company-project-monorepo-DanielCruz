"""Canonical department-scoped internal-reports collection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.access.catalog import Capability, is_admin, is_known_department
from app.access.permissions import (
    INSUFFICIENT_DEPARTMENT_DETAIL,
    assert_capability,
    assert_department_allowed,
    filter_department_rows,
    require_authenticated,
    require_create_record,
    require_delete_sensitive,
    require_update_record,
)
from app.schemas.internal_report import (
    InternalReportCreate,
    InternalReportPublic,
    InternalReportUpdate,
)
from app.schemas.user import UserInDB
from app.services import internal_report_service
from app.services.internal_report_service import InternalReportNotFoundError

router = APIRouter(prefix="/internal-reports", tags=["internal-reports"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")


@router.get("", response_model=list[InternalReportPublic])
def list_internal_reports(
    current_user: UserInDB = Depends(require_authenticated),
) -> list[InternalReportPublic]:
    assert_capability(current_user, Capability.read_department_data)
    return filter_department_rows(
        current_user,
        internal_report_service.list_reports(),
        lambda row: row.department_id,
    )


@router.post("", response_model=InternalReportPublic, status_code=status.HTTP_201_CREATED)
def create_internal_report(
    payload: InternalReportCreate,
    current_user: UserInDB = Depends(require_create_record),
) -> InternalReportPublic:
    department_id = payload.department_id or current_user.department_id
    if department_id is None or not is_known_department(department_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A known department_id is required",
        )
    if not is_admin(current_user.role) and department_id != current_user.department_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=INSUFFICIENT_DEPARTMENT_DETAIL,
        )
    return internal_report_service.create_report(
        department_id=department_id,
        title=payload.title,
        body=payload.body,
        created_by=current_user.id,
    )


@router.get("/{report_id}", response_model=InternalReportPublic)
def get_internal_report(
    report_id: str,
    current_user: UserInDB = Depends(require_authenticated),
) -> InternalReportPublic:
    assert_capability(current_user, Capability.read_department_data)
    try:
        report = internal_report_service.get_report(report_id)
    except InternalReportNotFoundError as exc:
        raise _not_found() from exc
    assert_department_allowed(current_user, report.department_id)
    return report


@router.patch("/{report_id}", response_model=InternalReportPublic)
def update_internal_report(
    report_id: str,
    payload: InternalReportUpdate,
    current_user: UserInDB = Depends(require_update_record),
) -> InternalReportPublic:
    try:
        report = internal_report_service.get_report(report_id)
    except InternalReportNotFoundError as exc:
        raise _not_found() from exc
    assert_department_allowed(current_user, report.department_id)
    return internal_report_service.update_report(report_id, payload)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_internal_report(
    report_id: str,
    current_user: UserInDB = Depends(require_delete_sensitive),
) -> None:
    try:
        report = internal_report_service.get_report(report_id)
    except InternalReportNotFoundError as exc:
        raise _not_found() from exc
    assert_department_allowed(current_user, report.department_id)
    internal_report_service.delete_report(report_id)
