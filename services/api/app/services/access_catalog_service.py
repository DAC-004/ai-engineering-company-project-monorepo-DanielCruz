"""TinyDB persistence for the independent Role and Department entities."""

from __future__ import annotations

from tinydb import Query

from app.access.catalog import DEPARTMENTS, ROLES
from app.db.tinydb import departments_table, roles_table
from app.schemas.access_admin import (
    DepartmentCreate,
    DepartmentPublic,
    DepartmentUpdate,
    RoleCreate,
    RolePublic,
    RoleUpdate,
)
from app.services.platform_access_seed import ensure_roles_and_departments


class AccessCatalogNotFoundError(LookupError):
    pass


class AccessCatalogConflictError(ValueError):
    pass


def _role_row(row: dict) -> RolePublic:
    return RolePublic.model_validate(
        {
            "id": row.get("id") or row.get("code"),
            "code": row.get("code") or row.get("id"),
            "name": row["name"],
            "rank": int(row["rank"]),
        }
    )


def _department_row(row: dict) -> DepartmentPublic:
    code = row.get("code") or row.get("id")
    return DepartmentPublic.model_validate(
        {"id": row.get("id") or code, "code": code, "name": row["name"]}
    )


def list_roles() -> list[RolePublic]:
    ensure_roles_and_departments()
    return [_role_row(row) for row in roles_table().all()]


def _find_role_row(role_id: str) -> dict | None:
    table = roles_table()
    return table.get(Query().id == role_id) or table.get(Query().code == role_id)


def get_role(role_id: str) -> RolePublic:
    ensure_roles_and_departments()
    row = _find_role_row(role_id)
    if row is None:
        raise AccessCatalogNotFoundError(role_id)
    return _role_row(row)


def create_role(payload: RoleCreate) -> RolePublic:
    ensure_roles_and_departments()
    table = roles_table()
    if _find_role_row(payload.code):
        raise AccessCatalogConflictError("A role with this code already exists.")
    record = {
        "id": payload.code,
        "code": payload.code,
        "name": payload.name,
        "rank": payload.rank,
    }
    table.insert(record)
    return _role_row(record)


def update_role(role_id: str, payload: RoleUpdate) -> RolePublic:
    ensure_roles_and_departments()
    table = roles_table()
    existing = _find_role_row(role_id)
    if existing is None:
        raise AccessCatalogNotFoundError(role_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates:
        table.update(updates, Query().id == existing["id"])
    refreshed = _find_role_row(existing["id"])
    return _role_row(refreshed)


def list_departments() -> list[DepartmentPublic]:
    ensure_roles_and_departments()
    return [_department_row(row) for row in departments_table().all()]


def _find_department_row(department_id: str) -> dict | None:
    table = departments_table()
    return table.get(Query().id == department_id) or table.get(Query().code == department_id)


def get_department(department_id: str) -> DepartmentPublic:
    ensure_roles_and_departments()
    row = _find_department_row(department_id)
    if row is None:
        raise AccessCatalogNotFoundError(department_id)
    return _department_row(row)


def create_department(payload: DepartmentCreate) -> DepartmentPublic:
    ensure_roles_and_departments()
    table = departments_table()
    if _find_department_row(payload.code):
        raise AccessCatalogConflictError("A department with this code already exists.")
    record = {"id": payload.code, "code": payload.code, "name": payload.name}
    table.insert(record)
    return _department_row(record)


def update_department(department_id: str, payload: DepartmentUpdate) -> DepartmentPublic:
    ensure_roles_and_departments()
    table = departments_table()
    existing = _find_department_row(department_id)
    if existing is None:
        raise AccessCatalogNotFoundError(department_id)
    updates = payload.model_dump(exclude_unset=True)
    if updates:
        table.update(updates, Query().id == existing["id"])
    refreshed = _find_department_row(existing["id"])
    return _department_row(refreshed)


def seed_catalog_constants() -> tuple[tuple[dict, ...], tuple[dict, ...]]:
    """Expose the specialized seed constants for tests."""
    return ROLES, DEPARTMENTS
