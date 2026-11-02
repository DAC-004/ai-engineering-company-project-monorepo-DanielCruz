"""Centralized HealthCore platform access control.

Catalog names are imported immediately. Permission helpers are resolved lazily
so `from app.access.catalog import ...` does not import FastAPI deps. That
avoids the cycle catalog -> package init -> permissions -> deps -> user_service
-> catalog while `app.core.deps` is still loading.
"""

from app.access.catalog import Capability, DepartmentId, has_capability

__all__ = [
    "Capability",
    "DepartmentId",
    "INSUFFICIENT_DEPARTMENT_DETAIL",
    "INSUFFICIENT_ROLE_DETAIL",
    "has_capability",
    "require_capability",
    "require_departments",
]

_PERMISSION_EXPORTS = frozenset(
    {
        "INSUFFICIENT_DEPARTMENT_DETAIL",
        "INSUFFICIENT_ROLE_DETAIL",
        "require_capability",
        "require_departments",
    }
)


def __getattr__(name: str):
    if name in _PERMISSION_EXPORTS:
        from app.access import permissions

        return getattr(permissions, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
