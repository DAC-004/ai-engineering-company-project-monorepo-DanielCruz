"""Admin-only department administration at /departments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.access.permissions import require_manage_access
from app.schemas.access_admin import DepartmentCreate, DepartmentPublic, DepartmentUpdate
from app.schemas.user import UserInDB
from app.services import access_catalog_service
from app.services.access_catalog_service import (
    AccessCatalogConflictError,
    AccessCatalogNotFoundError,
)

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentPublic])
def list_departments(
    _current_user: UserInDB = Depends(require_manage_access),
) -> list[DepartmentPublic]:
    return access_catalog_service.list_departments()


@router.post("", response_model=DepartmentPublic, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: DepartmentCreate,
    _current_user: UserInDB = Depends(require_manage_access),
) -> DepartmentPublic:
    try:
        return access_catalog_service.create_department(payload)
    except AccessCatalogConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/{department_id}", response_model=DepartmentPublic)
def get_department(
    department_id: str,
    _current_user: UserInDB = Depends(require_manage_access),
) -> DepartmentPublic:
    try:
        return access_catalog_service.get_department(department_id)
    except AccessCatalogNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        ) from exc


@router.put("/{department_id}", response_model=DepartmentPublic)
def update_department(
    department_id: str,
    payload: DepartmentUpdate,
    _current_user: UserInDB = Depends(require_manage_access),
) -> DepartmentPublic:
    try:
        return access_catalog_service.update_department(department_id, payload)
    except AccessCatalogNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        ) from exc
