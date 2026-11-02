"""Platform roles, departments, and capability hierarchy.

Source: specialized briefing titled BRIEFING — Roles and Permissions · HealthCore.
Role and department are independent axes. Admin cross-department access is a
role privilege; Admin still belongs to a department.
"""

from __future__ import annotations

from enum import Enum

from app.schemas.user import UserRole


class DepartmentId(str, Enum):
    clinical_operations = "clinical_operations"
    patient_experience = "patient_experience"
    revenue_cycle = "revenue_cycle"
    compliance = "compliance"
    people_workforce = "people_workforce"
    technology = "technology"


class Capability(str, Enum):
    authenticated = "authenticated"
    use_internal_tools = "use_internal_tools"
    read_department_data = "read_department_data"
    create_department_record = "create_department_record"
    update_department_record = "update_department_record"
    approve_department_record = "approve_department_record"
    delete_sensitive_record = "delete_sensitive_record"
    manage_users = "manage_users"
    manage_access = "manage_access"


DEPARTMENTS: tuple[dict[str, str], ...] = (
    {"id": DepartmentId.clinical_operations.value, "name": "Clinical Operations"},
    {"id": DepartmentId.patient_experience.value, "name": "Patient Experience and Access"},
    {"id": DepartmentId.revenue_cycle.value, "name": "Revenue Cycle and Billing"},
    {"id": DepartmentId.compliance.value, "name": "Compliance and Data Governance"},
    {"id": DepartmentId.people_workforce.value, "name": "People and Workforce"},
    {"id": DepartmentId.technology.value, "name": "Technology"},
)

DEPARTMENT_IDS: frozenset[str] = frozenset(item["id"] for item in DEPARTMENTS)
DEPARTMENT_NAME_BY_ID: dict[str, str] = {item["id"]: item["name"] for item in DEPARTMENTS}

RFP_DEPARTMENT_TO_PLATFORM: dict[str, str] = {
    "clinical": DepartmentId.clinical_operations.value,
    "revenue": DepartmentId.revenue_cycle.value,
    "compliance": DepartmentId.compliance.value,
}
PLATFORM_TO_RFP_DEPARTMENT: dict[str, str] = {
    platform_id: rfp_id for rfp_id, platform_id in RFP_DEPARTMENT_TO_PLATFORM.items()
}

ROLES: tuple[dict[str, str | int], ...] = (
    {
        "id": UserRole.employee.value,
        "code": UserRole.employee.value,
        "name": "Employee",
        "rank": 1,
        "description": "Create and read records in own department. Cannot approve, delete, or manage users/roles/departments.",
    },
    {
        "id": UserRole.supervisor.value,
        "code": UserRole.supervisor.value,
        "name": "Supervisor",
        "rank": 2,
        "description": "Employee plus update/approve in own department. Cannot delete, manage access, or see other departments.",
    },
    {
        "id": UserRole.admin.value,
        "code": UserRole.admin.value,
        "name": "Admin",
        "rank": 3,
        "description": "Supervisor plus delete, user/role/department administration, and cross-department visibility. Admin still belongs to a department.",
    },
)

_EMPLOYEE_CAPABILITIES: frozenset[Capability] = frozenset(
    {
        Capability.authenticated,
        Capability.use_internal_tools,
        Capability.read_department_data,
        Capability.create_department_record,
    }
)
_SUPERVISOR_CAPABILITIES: frozenset[Capability] = _EMPLOYEE_CAPABILITIES | frozenset(
    {
        Capability.update_department_record,
        Capability.approve_department_record,
    }
)
_ADMIN_CAPABILITIES: frozenset[Capability] = _SUPERVISOR_CAPABILITIES | frozenset(
    {
        Capability.delete_sensitive_record,
        Capability.manage_users,
        Capability.manage_access,
    }
)

ROLE_CAPABILITIES: dict[UserRole, frozenset[Capability]] = {
    UserRole.employee: _EMPLOYEE_CAPABILITIES,
    UserRole.supervisor: _SUPERVISOR_CAPABILITIES,
    UserRole.admin: _ADMIN_CAPABILITIES,
}

ROLE_RANK: dict[UserRole, int] = {
    UserRole.employee: 1,
    UserRole.supervisor: 2,
    UserRole.admin: 3,
}

LEGACY_ROLE_TO_PLATFORM: dict[str, UserRole] = {
    "user": UserRole.employee,
    "manager": UserRole.supervisor,
    "admin": UserRole.admin,
    UserRole.employee.value: UserRole.employee,
    UserRole.supervisor.value: UserRole.supervisor,
}


def department_name(department_id: str | None) -> str | None:
    if department_id is None:
        return None
    return DEPARTMENT_NAME_BY_ID.get(department_id)


def capabilities_for(role: UserRole) -> frozenset[Capability]:
    return ROLE_CAPABILITIES[role]


def has_capability(role: UserRole, capability: Capability) -> bool:
    return capability in ROLE_CAPABILITIES[role]


def normalize_role(raw_role: str | UserRole | None) -> UserRole:
    if isinstance(raw_role, UserRole):
        return raw_role
    if raw_role is None:
        return UserRole.employee
    mapped = LEGACY_ROLE_TO_PLATFORM.get(str(raw_role))
    if mapped is None:
        raise ValueError(f"Unknown role: {raw_role}")
    return mapped


def is_known_department(department_id: str | None) -> bool:
    return department_id is None or department_id in DEPARTMENT_IDS


def is_admin(role: UserRole) -> bool:
    return role == UserRole.admin
