"""Endpoint inventory for platform roles and departments.

Each route is classified from CONTEXT.md (Company Briefing), the assignment,
and the current API contract. Public routes stay public. Department scope is
applied only where the data belongs to a briefing department.
"""

from __future__ import annotations

from typing import Literal

AuthClass = Literal["public", "authenticated"]
DeptScope = str | None

# department_scope is a briefing department id, "rfp_mapped" for RFP section
# filtering, or None when the route is not department-scoped.
ENDPOINT_INVENTORY: tuple[dict[str, str | None], ...] = (
    {"method": "GET", "path": "/health", "auth": "public", "min_capability": None, "department_scope": None},
    {"method": "POST", "path": "/auth/login", "auth": "public", "min_capability": None, "department_scope": None},
    {"method": "POST", "path": "/auth/forgot-password", "auth": "public", "min_capability": None, "department_scope": None},
    {"method": "POST", "path": "/auth/reset-password", "auth": "public", "min_capability": None, "department_scope": None},
    {"method": "GET", "path": "/auth/me", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "POST", "path": "/auth/change-password", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "POST", "path": "/users", "auth": "authenticated", "min_capability": "manage_users", "department_scope": None},
    {"method": "GET", "path": "/users", "auth": "authenticated", "min_capability": "manage_users", "department_scope": None},
    {"method": "PATCH", "path": "/users/{user_id}/assignment", "auth": "authenticated", "min_capability": "manage_users", "department_scope": None},
    {"method": "GET", "path": "/users/{user_id}", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "PUT", "path": "/users/{user_id}", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "DELETE", "path": "/users/{user_id}", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "GET", "path": "/profiles/me", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "PUT", "path": "/profiles/me", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "GET", "path": "/access/roles", "auth": "authenticated", "min_capability": "manage_access", "department_scope": None},
    {"method": "GET", "path": "/access/departments", "auth": "authenticated", "min_capability": "manage_access", "department_scope": None},
    {"method": "GET", "path": "/roles", "auth": "authenticated", "min_capability": "manage_access", "department_scope": None},
    {"method": "POST", "path": "/roles", "auth": "authenticated", "min_capability": "manage_access", "department_scope": None},
    {"method": "GET", "path": "/roles/{id}", "auth": "authenticated", "min_capability": "manage_access", "department_scope": None},
    {"method": "PUT", "path": "/roles/{id}", "auth": "authenticated", "min_capability": "manage_access", "department_scope": None},
    {"method": "GET", "path": "/departments", "auth": "authenticated", "min_capability": "manage_access", "department_scope": None},
    {"method": "POST", "path": "/departments", "auth": "authenticated", "min_capability": "manage_access", "department_scope": None},
    {"method": "GET", "path": "/departments/{id}", "auth": "authenticated", "min_capability": "manage_access", "department_scope": None},
    {"method": "PUT", "path": "/departments/{id}", "auth": "authenticated", "min_capability": "manage_access", "department_scope": None},
    {"method": "GET", "path": "/internal-reports", "auth": "authenticated", "min_capability": "read_department_data", "department_scope": "caller_or_admin"},
    {"method": "POST", "path": "/internal-reports", "auth": "authenticated", "min_capability": "create_department_record", "department_scope": "caller_or_admin"},
    {"method": "GET", "path": "/internal-reports/{id}", "auth": "authenticated", "min_capability": "read_department_data", "department_scope": "caller_or_admin"},
    {"method": "PATCH", "path": "/internal-reports/{id}", "auth": "authenticated", "min_capability": "update_department_record", "department_scope": "caller_or_admin"},
    {"method": "DELETE", "path": "/internal-reports/{id}", "auth": "authenticated", "min_capability": "delete_sensitive_record", "department_scope": "caller_or_admin"},
    {"method": "POST", "path": "/api/incidents/analyze", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "GET", "path": "/api/incidents/results", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "GET", "path": "/api/incidents/results/summary", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "GET", "path": "/api/incidents/results/export", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "DELETE", "path": "/api/incidents/results", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "POST", "path": "/api/incidents", "auth": "authenticated", "min_capability": "create_department_record", "department_scope": "caller_or_admin"},
    {"method": "GET", "path": "/api/incidents", "auth": "authenticated", "min_capability": "authenticated", "department_scope": "caller_or_admin"},
    {"method": "GET", "path": "/api/incidents/summary", "auth": "authenticated", "min_capability": "authenticated", "department_scope": "caller_or_admin"},
    {"method": "GET", "path": "/api/incidents/{incident_id}", "auth": "authenticated", "min_capability": "authenticated", "department_scope": "caller_or_admin"},
    {"method": "PATCH", "path": "/api/incidents/{incident_id}/status", "auth": "authenticated", "min_capability": "update_department_record", "department_scope": "caller_or_admin"},
    {"method": "GET", "path": "/inventory/products", "auth": "authenticated", "min_capability": "authenticated", "department_scope": "caller_or_admin"},
    {"method": "POST", "path": "/inventory/products", "auth": "authenticated", "min_capability": "create_department_record", "department_scope": "caller_or_admin"},
    {"method": "GET", "path": "/inventory/products/{id}", "auth": "authenticated", "min_capability": "authenticated", "department_scope": "caller_or_admin"},
    {"method": "PUT", "path": "/inventory/products/{id}", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "PATCH", "path": "/inventory/products/{id}", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "POST", "path": "/inventory/orders/inbound", "auth": "authenticated", "min_capability": "create_department_record", "department_scope": "caller_or_admin"},
    {"method": "POST", "path": "/inventory/orders/outbound", "auth": "authenticated", "min_capability": "create_department_record", "department_scope": "caller_or_admin"},
    {"method": "GET", "path": "/inventory/orders", "auth": "authenticated", "min_capability": "authenticated", "department_scope": "caller_or_admin"},
    {"method": "POST", "path": "/telemetry/events", "auth": "public", "min_capability": None, "department_scope": None},
    {"method": "GET", "path": "/telemetry/report", "auth": "authenticated", "min_capability": "read_department_data", "department_scope": "technology"},
    {"method": "GET", "path": "/tasks/{task_id}", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "GET", "path": "/reporting/monthly-clinic-supply-performance", "auth": "authenticated", "min_capability": "read_department_data", "department_scope": "clinical_operations"},
    {"method": "GET", "path": "/reporting/pipeline-runs/latest", "auth": "authenticated", "min_capability": "read_department_data", "department_scope": "technology"},
    {"method": "POST", "path": "/reporting/pipeline-runs", "auth": "authenticated", "min_capability": "update_department_record", "department_scope": "technology"},
    {"method": "POST", "path": "/rfp/tickets", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "POST", "path": "/rfp/tickets/{ticket_id}/response", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "POST", "path": "/rfp/tickets/{ticket_id}/approval", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "POST", "path": "/rfp/tickets/{ticket_id}/approval/{department_id}", "auth": "authenticated", "min_capability": "approve_department_record", "department_scope": "rfp_mapped"},
    {"method": "GET", "path": "/rfp/tickets/{ticket_id}/final-document", "auth": "authenticated", "min_capability": "read_department_data", "department_scope": "rfp_mapped"},
    {"method": "GET", "path": "/rfp/tickets/stream", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
    {"method": "GET", "path": "/rfp/tickets/{ticket_id}", "auth": "authenticated", "min_capability": "read_department_data", "department_scope": "rfp_mapped"},
    {"method": "POST", "path": "/suppliers", "auth": "authenticated", "min_capability": "create_department_record", "department_scope": "caller_or_admin"},
    {"method": "GET", "path": "/suppliers", "auth": "authenticated", "min_capability": "authenticated", "department_scope": "caller_or_admin"},
    {"method": "GET", "path": "/suppliers/{supplier_id}", "auth": "authenticated", "min_capability": "authenticated", "department_scope": "caller_or_admin"},
    {"method": "PATCH", "path": "/suppliers/{supplier_id}/rate", "auth": "authenticated", "min_capability": "update_department_record", "department_scope": "caller_or_admin"},
    {"method": "PATCH", "path": "/suppliers/{supplier_id}/status", "auth": "authenticated", "min_capability": "update_department_record", "department_scope": "caller_or_admin"},
    {"method": "DELETE", "path": "/suppliers/{supplier_id}", "auth": "authenticated", "min_capability": "delete_sensitive_record", "department_scope": "caller_or_admin"},
    {"method": "POST", "path": "/knowledge/query", "auth": "public", "min_capability": None, "department_scope": None},
    {"method": "GET", "path": "/agent/guardrails/summary", "auth": "public", "min_capability": None, "department_scope": None},
    {"method": "POST", "path": "/agent/query", "auth": "public", "min_capability": None, "department_scope": None},
    {"method": "WEBSOCKET", "path": "/ws/chat/{session_id}", "auth": "authenticated", "min_capability": "authenticated", "department_scope": None},
)
