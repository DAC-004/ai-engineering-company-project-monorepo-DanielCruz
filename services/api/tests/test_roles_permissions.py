"""Compliance tests for HealthCore roles and department independence."""

from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

from fastapi.testclient import TestClient
from tinydb import Query

from app.access.permissions import INSUFFICIENT_DEPARTMENT_DETAIL, INSUFFICIENT_ROLE_DETAIL
from app.database import _resolved_db_path
from app.db.tinydb import departments_table, roles_table, users_table
from app.schemas.user import UserCreate, UserRole
from app.services import internal_report_service, user_service
from app.services.internal_report_service import InternalReportNotFoundError
from app.services.platform_access_seed import ensure_roles_and_departments

SEED_PASSWORD = "SecurePass1!"


def _login(client: TestClient, email: str, password: str = SEED_PASSWORD) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_evaluation_users() -> dict[str, object]:
    ensure_roles_and_departments()
    specs = (
        ("marcus.clinical@healthcore.example", UserRole.supervisor, "clinical_operations", "Dr. Marcus Reid"),
        ("tom.billing@healthcore.example", UserRole.supervisor, "revenue_cycle", "Tom Callahan"),
        ("priya.access@healthcore.example", UserRole.employee, "patient_experience", "Priya Nair"),
        ("james.admin@healthcore.example", UserRole.admin, "technology", "James Osei"),
    )
    users = {}
    for email, role, department_id, _name in specs:
        existing = user_service.get_user_by_email(email)
        if existing is None:
            existing = user_service.create_user(
                UserCreate(email=email, password=SEED_PASSWORD),
                role=role,
                department_id=department_id,
            )
        users[email] = existing
    reports = {row.title: row for row in internal_report_service.list_reports()}
    if "Austin North — documentation time spike" not in reports:
        reports["Austin North — documentation time spike"] = internal_report_service.create_report(
            department_id="clinical_operations",
            title="Austin North — documentation time spike",
            body="Average documentation minutes per encounter up 12% week over week. No patient identifiers.",
            created_by=users["marcus.clinical@healthcore.example"].id,
        )
    if "US denial rate — coding mismatch cluster" not in reports:
        reports["US denial rate — coding mismatch cluster"] = internal_report_service.create_report(
            department_id="revenue_cycle",
            title="US denial rate — coding mismatch cluster",
            body="14% denial rate driven by three CPT mismatch patterns. No member IDs in this note.",
            created_by=users["tom.billing@healthcore.example"].id,
        )
    return {
        "users": users,
        "clinical_report": reports["Austin North — documentation time spike"],
        "revenue_report": reports["US denial rate — coding mismatch cluster"],
    }


def test_j1_employee_supervisor_update_is_403(client: TestClient) -> None:
    seeded = _seed_evaluation_users()
    headers = _login(client, "priya.access@healthcore.example")
    report_id = seeded["clinical_report"].id
    response = client.patch(
        f"/internal-reports/{report_id}",
        json={"title": "Unauthorized rewrite"},
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == INSUFFICIENT_ROLE_DETAIL


def test_j2_supervisor_admin_routes_are_403(client: TestClient) -> None:
    seeded = _seed_evaluation_users()
    headers = _login(client, "marcus.clinical@healthcore.example")
    roles = client.get("/roles", headers=headers)
    assert roles.status_code == 403
    assert roles.json()["detail"] == INSUFFICIENT_ROLE_DETAIL

    assignment = client.patch(
        f"/users/{seeded['users']['tom.billing@healthcore.example'].id}/assignment",
        json={"department_id": "compliance"},
        headers=headers,
    )
    assert assignment.status_code == 403
    assert assignment.json()["detail"] == INSUFFICIENT_ROLE_DETAIL


def test_j3_marcus_cannot_get_toms_revenue_report(client: TestClient) -> None:
    seeded = _seed_evaluation_users()
    headers = _login(client, "marcus.clinical@healthcore.example")
    response = client.get(
        f"/internal-reports/{seeded['revenue_report'].id}",
        headers=headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL
    assert response.json().get("title") is None


def test_employee_and_supervisor_cannot_change_own_or_other_user_role(
    client: TestClient,
) -> None:
    seeded = _seed_evaluation_users()
    priya = seeded["users"]["priya.access@healthcore.example"]
    marcus = seeded["users"]["marcus.clinical@healthcore.example"]
    tom = seeded["users"]["tom.billing@healthcore.example"]
    priya_headers = _login(client, priya.email)
    marcus_headers = _login(client, marcus.email)

    unauthenticated = client.patch(
        f"/users/{priya.id}/assignment",
        json={"role_id": "admin"},
    )
    assert unauthenticated.status_code == 401

    priya_self_put = client.put(
        f"/users/{priya.id}",
        json={"role": "admin"},
        headers=priya_headers,
    )
    assert priya_self_put.status_code == 403
    assert priya_self_put.json()["detail"] == INSUFFICIENT_ROLE_DETAIL

    priya_other_put = client.put(
        f"/users/{marcus.id}",
        json={"role": "admin"},
        headers=priya_headers,
    )
    assert priya_other_put.status_code == 403

    priya_self_assign = client.patch(
        f"/users/{priya.id}/assignment",
        json={"role_id": "admin"},
        headers=priya_headers,
    )
    assert priya_self_assign.status_code == 403
    assert priya_self_assign.json()["detail"] == INSUFFICIENT_ROLE_DETAIL

    priya_other_assign = client.patch(
        f"/users/{marcus.id}/assignment",
        json={"role_id": "admin"},
        headers=priya_headers,
    )
    assert priya_other_assign.status_code == 403
    assert priya_other_assign.json()["detail"] == INSUFFICIENT_ROLE_DETAIL

    marcus_self_put = client.put(
        f"/users/{marcus.id}",
        json={"role": "admin"},
        headers=marcus_headers,
    )
    assert marcus_self_put.status_code == 403
    assert marcus_self_put.json()["detail"] == INSUFFICIENT_ROLE_DETAIL

    marcus_other_put = client.put(
        f"/users/{tom.id}",
        json={"role": "employee"},
        headers=marcus_headers,
    )
    assert marcus_other_put.status_code == 403

    marcus_self_assign = client.patch(
        f"/users/{marcus.id}/assignment",
        json={"role_id": "admin"},
        headers=marcus_headers,
    )
    assert marcus_self_assign.status_code == 403
    assert marcus_self_assign.json()["detail"] == INSUFFICIENT_ROLE_DETAIL

    after_priya = user_service.get_user_by_id(priya.id)
    after_marcus = user_service.get_user_by_id(marcus.id)
    after_tom = user_service.get_user_by_id(tom.id)
    assert after_priya is not None and after_priya.role == UserRole.employee
    assert after_marcus is not None and after_marcus.role == UserRole.supervisor
    assert after_tom is not None and after_tom.role == UserRole.supervisor


def test_j4_assignment_is_independent(client: TestClient) -> None:
    seeded = _seed_evaluation_users()
    admin_headers = _login(client, "james.admin@healthcore.example")
    tom = seeded["users"]["tom.billing@healthcore.example"]
    marcus = seeded["users"]["marcus.clinical@healthcore.example"]

    tom_update = client.patch(
        f"/users/{tom.id}/assignment",
        json={"department_id": "compliance"},
        headers=admin_headers,
    )
    assert tom_update.status_code == 200, tom_update.text
    tom_body = tom_update.json()
    assert tom_body["department_id"] == "compliance"
    assert tom_body["role"] == "supervisor"
    assert tom_body["role_id"] == "supervisor"

    marcus_update = client.patch(
        f"/users/{marcus.id}/assignment",
        json={"role_id": "employee"},
        headers=admin_headers,
    )
    assert marcus_update.status_code == 200, marcus_update.text
    marcus_body = marcus_update.json()
    assert marcus_body["role"] == "employee"
    assert marcus_body["role_id"] == "employee"
    assert marcus_body["department_id"] == "clinical_operations"


def test_j5_permission_checks_are_centralized() -> None:
    source = inspect.getsource(__import__("app.access.permissions", fromlist=["require_capability"]))
    assert "def require_capability" in source
    assert "def require_departments" in source
    assert "def assert_department_allowed" in source

    api_root = Path(__file__).resolve().parents[1]
    router_files = [
        api_root / "app/routers/internal_reports.py",
        api_root / "app/routers/roles.py",
        api_root / "app/routers/departments.py",
        api_root / "app/routers/users.py",
        api_root / "app/routers/incident_manager.py",
        api_root / "app/routers/suppliers.py",
        api_root / "app/routers/inventory.py",
    ]
    for path in router_files:
        text = path.read_text(encoding="utf-8")
        assert "from app.access.permissions import" in text
        assert "require_" in text


def test_admin_sees_all_internal_reports_and_keeps_technology_membership(
    client: TestClient,
) -> None:
    seeded = _seed_evaluation_users()
    headers = _login(client, "james.admin@healthcore.example")
    listed = client.get("/internal-reports", headers=headers)
    assert listed.status_code == 200
    titles = {row["title"] for row in listed.json()}
    assert "Austin North — documentation time spike" in titles
    assert "US denial rate — coding mismatch cluster" in titles

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "admin"
    assert body["department_id"] == "technology"

    other = client.get(f"/internal-reports/{seeded['revenue_report'].id}", headers=headers)
    assert other.status_code == 200
    assert other.json()["department_id"] == "revenue_cycle"


def test_supervisor_list_is_own_department_only(client: TestClient) -> None:
    _seed_evaluation_users()
    headers = _login(client, "marcus.clinical@healthcore.example")
    listed = client.get("/internal-reports", headers=headers)
    assert listed.status_code == 200
    rows = listed.json()
    assert rows
    assert all(row["department_id"] == "clinical_operations" for row in rows)
    assert all(row["title"] != "US denial rate — coding mismatch cluster" for row in rows)


def test_seeded_roles_and_departments_match_specialized_codes(client: TestClient) -> None:
    _seed_evaluation_users()
    headers = _login(client, "james.admin@healthcore.example")
    roles = client.get("/roles", headers=headers)
    departments = client.get("/departments", headers=headers)
    assert roles.status_code == 200
    assert departments.status_code == 200
    role_codes = {row["code"]: row for row in roles.json()}
    assert role_codes["employee"]["rank"] == 1
    assert role_codes["supervisor"]["rank"] == 2
    assert role_codes["admin"]["rank"] == 3
    department_codes = {row["code"] for row in departments.json()}
    assert department_codes == {
        "clinical_operations",
        "patient_experience",
        "revenue_cycle",
        "compliance",
        "people_workforce",
        "technology",
    }


_INCIDENT_CREATE = {
    "title": "Department-scoped incident",
    "description": "Operational note only. No patient identifiers.",
    "category": "clinical_equipment",
    "origin": "internal",
    "branch": "austin_north",
}

_SUPPLIER_CREATE = {
    "name": "Department-scoped supplier",
    "country": "USA",
    "categories": ["medical_supplies"],
    "monthly_rate": 1100.0,
    "currency": "USD",
    "status": "active",
}


def test_roles_and_departments_are_separate_persisted_entities(
    client: TestClient,
) -> None:
    _seed_evaluation_users()
    _login(client, "james.admin@healthcore.example")
    role_ids = {row["id"] for row in roles_table().all()}
    department_ids = {row["id"] for row in departments_table().all()}
    assert role_ids == {"employee", "supervisor", "admin"}
    assert department_ids == {
        "clinical_operations",
        "patient_experience",
        "revenue_cycle",
        "compliance",
        "people_workforce",
        "technology",
    }
    assert role_ids.isdisjoint(department_ids)


def test_user_row_stores_role_id_independently_of_department_id(
    client: TestClient,
) -> None:
    seeded = _seed_evaluation_users()
    tom = seeded["users"]["tom.billing@healthcore.example"]
    row = users_table().get(Query().id == tom.id)
    assert row is not None
    assert row["id"] == tom.id
    assert row["email"] == "tom.billing@healthcore.example"
    assert row["role"] == "supervisor"
    assert row["role_id"] == "supervisor"
    assert row["department_id"] == "revenue_cycle"
    assert row["role_id"] != row["department_id"]
    role_row = roles_table().get(Query().id == row["role_id"]) or roles_table().get(
        Query().code == row["role_id"]
    )
    assert role_row is not None
    assert role_row["id"] == "supervisor"
    assert role_row["code"] == "supervisor"

    admin_headers = _login(client, "james.admin@healthcore.example")
    patched = client.patch(
        f"/users/{tom.id}/assignment",
        json={"department_id": "compliance"},
        headers=admin_headers,
    )
    assert patched.status_code == 200, patched.text
    stored = users_table().get(Query().id == tom.id)
    assert stored is not None
    assert stored["id"] == tom.id
    assert stored["email"] == "tom.billing@healthcore.example"
    assert stored["role_id"] == "supervisor"
    assert stored["role"] == "supervisor"
    assert stored["department_id"] == "compliance"


def test_incident_manager_department_scope_and_admin_cross_department(
    client: TestClient,
) -> None:
    _seed_evaluation_users()
    marcus = _login(client, "marcus.clinical@healthcore.example")
    tom = _login(client, "tom.billing@healthcore.example")
    priya = _login(client, "priya.access@healthcore.example")
    james = _login(client, "james.admin@healthcore.example")

    clinical = client.post("/api/incidents", json=_INCIDENT_CREATE, headers=marcus)
    revenue = client.post(
        "/api/incidents",
        json={**_INCIDENT_CREATE, "title": "Revenue-cycle incident"},
        headers=tom,
    )
    assert clinical.status_code == 200, clinical.text
    assert revenue.status_code == 200, revenue.text
    clinical_id = clinical.json()["id"]
    revenue_id = revenue.json()["id"]
    assert clinical.json()["department_id"] == "clinical_operations"
    assert revenue.json()["department_id"] == "revenue_cycle"

    listed = client.get("/api/incidents", headers=marcus)
    assert listed.status_code == 200
    rows = listed.json()
    assert rows
    assert all(row["department_id"] == "clinical_operations" for row in rows)
    assert all(row["id"] != revenue_id for row in rows)

    denied = client.get(f"/api/incidents/{revenue_id}", headers=marcus)
    assert denied.status_code == 403
    assert denied.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL
    assert denied.json().get("title") is None

    employee_denied = client.get(f"/api/incidents/{clinical_id}", headers=priya)
    assert employee_denied.status_code == 403
    assert employee_denied.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL

    role_denied = client.patch(
        f"/api/incidents/{clinical_id}/status",
        json={"status": "in_progress"},
        headers=priya,
    )
    assert role_denied.status_code == 403
    assert role_denied.json()["detail"] == INSUFFICIENT_ROLE_DETAIL

    admin_get = client.get(f"/api/incidents/{revenue_id}", headers=james)
    assert admin_get.status_code == 200
    assert admin_get.json()["department_id"] == "revenue_cycle"

    admin_list = client.get("/api/incidents", headers=james)
    assert admin_list.status_code == 200
    admin_ids = {row["id"] for row in admin_list.json()}
    assert clinical_id in admin_ids
    assert revenue_id in admin_ids

    me = client.get("/auth/me", headers=james)
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    assert me.json()["department_id"] == "technology"


def test_supplier_department_scope_and_admin_cross_department(
    client: TestClient,
) -> None:
    _seed_evaluation_users()
    from app.database import _default_db_path

    isolated_suppliers = Path(os.environ["SUPPLIERS_DB_PATH"])
    assert _resolved_db_path() == isolated_suppliers
    assert isolated_suppliers != _default_db_path

    marcus = _login(client, "marcus.clinical@healthcore.example")
    tom = _login(client, "tom.billing@healthcore.example")
    priya = _login(client, "priya.access@healthcore.example")
    james = _login(client, "james.admin@healthcore.example")

    clinical = client.post(
        "/suppliers",
        json={**_SUPPLIER_CREATE, "name": "Clinical ops supplier"},
        headers=marcus,
    )
    revenue = client.post(
        "/suppliers",
        json={**_SUPPLIER_CREATE, "name": "Revenue cycle supplier"},
        headers=tom,
    )
    assert clinical.status_code == 201, clinical.text
    assert revenue.status_code == 201, revenue.text
    clinical_id = clinical.json()["id"]
    revenue_id = revenue.json()["id"]
    assert clinical.json()["department_id"] == "clinical_operations"
    assert revenue.json()["department_id"] == "revenue_cycle"

    # Specialized Roles: Employee may create records in own department. This
    # POST inserts a supplier row; it is not a Supervisor update/approve.
    employee_create = client.post(
        "/suppliers",
        json={**_SUPPLIER_CREATE, "name": "Patient experience supplier"},
        headers=priya,
    )
    assert employee_create.status_code == 201, employee_create.text
    priya_id = employee_create.json()["id"]
    assert employee_create.json()["department_id"] == "patient_experience"
    assert employee_create.json()["monthly_rate"] == 1100.0

    persisted = client.get(f"/suppliers/{priya_id}", headers=priya)
    assert persisted.status_code == 200
    assert persisted.json()["id"] == priya_id
    assert persisted.json()["department_id"] == "patient_experience"

    priya_list = client.get("/suppliers", headers=priya)
    assert priya_list.status_code == 200
    priya_rows = priya_list.json()
    assert any(row["id"] == priya_id for row in priya_rows)
    assert all(row["department_id"] == "patient_experience" for row in priya_rows)
    assert all(row["id"] not in {clinical_id, revenue_id} for row in priya_rows)

    other_employee = user_service.create_user(
        UserCreate(email="claire.compliance@healthcore.example", password=SEED_PASSWORD),
        role=UserRole.employee,
        department_id="compliance",
    )
    claire = _login(client, other_employee.email)
    other_employee_get = client.get(f"/suppliers/{priya_id}", headers=claire)
    assert other_employee_get.status_code == 403
    assert other_employee_get.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL
    claire_list = client.get("/suppliers", headers=claire)
    assert claire_list.status_code == 200
    assert all(row["id"] != priya_id for row in claire_list.json())

    listed = client.get("/suppliers", headers=marcus)
    assert listed.status_code == 200
    rows = listed.json()
    assert rows
    assert all(row["department_id"] == "clinical_operations" for row in rows)
    assert all(row["id"] not in {revenue_id, priya_id} for row in rows)

    denied = client.get(f"/suppliers/{revenue_id}", headers=marcus)
    assert denied.status_code == 403
    assert denied.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL

    supervisor_cross = client.get(f"/suppliers/{priya_id}", headers=tom)
    assert supervisor_cross.status_code == 403
    assert supervisor_cross.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL
    tom_list = client.get("/suppliers", headers=tom)
    assert tom_list.status_code == 200
    assert all(row["id"] != priya_id for row in tom_list.json())

    employee_role = client.patch(
        f"/suppliers/{clinical_id}/rate",
        json={"monthly_rate": 1300.0},
        headers=priya,
    )
    assert employee_role.status_code == 403
    assert employee_role.json()["detail"] == INSUFFICIENT_ROLE_DETAIL

    own_update = client.patch(
        f"/suppliers/{priya_id}/rate",
        json={"monthly_rate": 1300.0},
        headers=priya,
    )
    assert own_update.status_code == 403
    assert own_update.json()["detail"] == INSUFFICIENT_ROLE_DETAIL
    unchanged = client.get(f"/suppliers/{priya_id}", headers=priya)
    assert unchanged.status_code == 200
    assert unchanged.json()["monthly_rate"] == 1100.0

    admin_get = client.get(f"/suppliers/{revenue_id}", headers=james)
    assert admin_get.status_code == 200
    assert admin_get.json()["department_id"] == "revenue_cycle"

    admin_list = client.get("/suppliers", headers=james)
    assert admin_list.status_code == 200
    admin_ids = {row["id"] for row in admin_list.json()}
    assert clinical_id in admin_ids
    assert revenue_id in admin_ids
    assert priya_id in admin_ids

    me = client.get("/auth/me", headers=james)
    assert me.status_code == 200
    assert me.json()["department_id"] == "technology"


def test_inventory_department_scope_and_admin_cross_department(
    client: TestClient,
) -> None:
    _seed_evaluation_users()
    marcus = _login(client, "marcus.clinical@healthcore.example")
    tom = _login(client, "tom.billing@healthcore.example")
    priya = _login(client, "priya.access@healthcore.example")
    james = _login(client, "james.admin@healthcore.example")

    clinical_list = client.get("/inventory/products", headers=marcus)
    assert clinical_list.status_code == 200
    clinical_rows = clinical_list.json()
    assert clinical_rows
    assert all(row["department_id"] == "clinical_operations" for row in clinical_rows)
    clinical_id = clinical_rows[0]["id"]

    employee_create = client.post(
        "/inventory/products",
        json={
            "name": "Patient-experience tagged gauze",
            "sku": "PE-DEPT-GAUZE-001",
            "category": "consumables",
            "unit": "box",
            "country": "US",
        },
        headers=priya,
    )
    # Specialized Roles: Employee may create records in own department. This
    # POST inserts a catalog row; it is not a Supervisor update/approve.
    assert employee_create.status_code == 201, employee_create.text
    priya_id = employee_create.json()["id"]
    assert employee_create.json()["department_id"] == "patient_experience"

    created = client.post(
        "/inventory/products",
        json={
            "name": "Revenue tagged gauze",
            "sku": "REV-DEPT-GAUZE-001",
            "category": "consumables",
            "unit": "box",
            "country": "US",
        },
        headers=tom,
    )
    assert created.status_code == 201, created.text
    revenue_id = created.json()["id"]
    assert created.json()["department_id"] == "revenue_cycle"

    tom_list = client.get("/inventory/products", headers=tom)
    assert tom_list.status_code == 200
    tom_rows = tom_list.json()
    assert tom_rows
    assert all(row["department_id"] == "revenue_cycle" for row in tom_rows)
    assert all(row["id"] != clinical_id for row in tom_rows)
    assert all(row["id"] != priya_id for row in tom_rows)

    priya_cross = client.get(f"/inventory/products/{clinical_id}", headers=priya)
    assert priya_cross.status_code == 403
    assert priya_cross.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL

    denied = client.get(f"/inventory/products/{clinical_id}", headers=tom)
    assert denied.status_code == 403
    assert denied.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL
    assert denied.json().get("name") is None

    admin_get = client.get(f"/inventory/products/{revenue_id}", headers=james)
    assert admin_get.status_code == 200
    assert admin_get.json()["department_id"] == "revenue_cycle"

    admin_list = client.get("/inventory/products", headers=james)
    assert admin_list.status_code == 200
    admin_ids = {row["id"] for row in admin_list.json()}
    assert clinical_id in admin_ids
    assert revenue_id in admin_ids
    assert priya_id in admin_ids

    tom_cross_inbound = client.post(
        "/inventory/orders/inbound",
        json={
            "supply_id": clinical_id,
            "quantity": 2,
            "vendor_name": "Cross department inbound",
            "clinic_id": 1,
        },
        headers=tom,
    )
    assert tom_cross_inbound.status_code == 403
    assert tom_cross_inbound.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL

    inbound_clinical = client.post(
        "/inventory/orders/inbound",
        json={
            "supply_id": clinical_id,
            "quantity": 2,
            "vendor_name": "Clinical inbound vendor",
            "clinic_id": 1,
        },
        headers=marcus,
    )
    inbound_revenue = client.post(
        "/inventory/orders/inbound",
        json={
            "supply_id": revenue_id,
            "quantity": 3,
            "vendor_name": "Revenue inbound vendor",
            "clinic_id": 1,
        },
        headers=tom,
    )
    admin_cross_inbound = client.post(
        "/inventory/orders/inbound",
        json={
            "supply_id": clinical_id,
            "quantity": 1,
            "vendor_name": "Admin clinical inbound",
            "clinic_id": 1,
        },
        headers=james,
    )
    assert inbound_clinical.status_code == 201, inbound_clinical.text
    assert inbound_revenue.status_code == 201, inbound_revenue.text
    assert admin_cross_inbound.status_code == 201, admin_cross_inbound.text

    rejected = client.put(f"/inventory/products/{clinical_id}", headers=tom)
    assert rejected.status_code == 405
    patched = client.patch(f"/inventory/products/{clinical_id}", json={}, headers=tom)
    assert patched.status_code == 405

    tom_orders = client.get("/inventory/orders", headers=tom)
    assert tom_orders.status_code == 200
    assert tom_orders.json()
    assert all(row["supply_id"] == revenue_id for row in tom_orders.json())

    marcus_orders = client.get("/inventory/orders", headers=marcus)
    assert marcus_orders.status_code == 200
    assert all(row["supply_id"] != revenue_id for row in marcus_orders.json())

    admin_orders = client.get("/inventory/orders", headers=james)
    assert admin_orders.status_code == 200
    admin_supply_ids = {row["supply_id"] for row in admin_orders.json()}
    assert clinical_id in admin_supply_ids
    assert revenue_id in admin_supply_ids

    me = client.get("/auth/me", headers=james)
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    assert me.json()["department_id"] == "technology"


def test_monthly_clinic_supply_report_is_clinical_owned_data(
    client: TestClient,
) -> None:
    """Clinic-month KPIs are Clinical Operations data. Tom's 403 is department denial."""
    _seed_evaluation_users()
    tom = _login(client, "tom.billing@healthcore.example")
    marcus = _login(client, "marcus.clinical@healthcore.example")
    james = _login(client, "james.admin@healthcore.example")

    denied = client.get("/reporting/monthly-clinic-supply-performance", headers=tom)
    assert denied.status_code == 403
    assert denied.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL

    clinical = client.get("/reporting/monthly-clinic-supply-performance", headers=marcus)
    assert clinical.status_code in (200, 404)

    admin = client.get("/reporting/monthly-clinic-supply-performance", headers=james)
    assert admin.status_code in (200, 404)
    me = client.get("/auth/me", headers=james)
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    assert me.json()["department_id"] == "technology"


def test_e10_admin_deletes_cross_department_report_employee_and_supervisor_cannot(
    client: TestClient,
) -> None:
    """Admin DELETE of another department's report; Employee/Supervisor own-dept DELETE is 403."""
    seeded = _seed_evaluation_users()
    priya = _login(client, "priya.access@healthcore.example")
    marcus = _login(client, "marcus.clinical@healthcore.example")
    james = _login(client, "james.admin@healthcore.example")

    employee_report = internal_report_service.create_report(
        department_id="patient_experience",
        title="Disposable PE queue note",
        body="Operational access note. No patient identifiers.",
        created_by=seeded["users"]["priya.access@healthcore.example"].id,
    )
    supervisor_report = internal_report_service.create_report(
        department_id="clinical_operations",
        title="Disposable clinical ops note",
        body="Operational documentation note. No patient identifiers.",
        created_by=seeded["users"]["marcus.clinical@healthcore.example"].id,
    )
    admin_target = internal_report_service.create_report(
        department_id="revenue_cycle",
        title="Disposable revenue ops note",
        body="Operational billing note. No member IDs.",
        created_by=seeded["users"]["tom.billing@healthcore.example"].id,
    )

    employee_delete = client.delete(f"/internal-reports/{employee_report.id}", headers=priya)
    assert employee_delete.status_code == 403
    assert employee_delete.json()["detail"] == INSUFFICIENT_ROLE_DETAIL
    employee_get = client.get(f"/internal-reports/{employee_report.id}", headers=priya)
    assert employee_get.status_code == 200
    assert employee_get.json()["id"] == employee_report.id
    assert employee_get.json()["title"] == employee_report.title
    assert internal_report_service.get_report(employee_report.id).id == employee_report.id

    supervisor_delete = client.delete(
        f"/internal-reports/{supervisor_report.id}",
        headers=marcus,
    )
    assert supervisor_delete.status_code == 403
    assert supervisor_delete.json()["detail"] == INSUFFICIENT_ROLE_DETAIL
    supervisor_get = client.get(f"/internal-reports/{supervisor_report.id}", headers=marcus)
    assert supervisor_get.status_code == 200
    assert supervisor_get.json()["id"] == supervisor_report.id
    assert internal_report_service.get_report(supervisor_report.id).id == supervisor_report.id

    # Established contract: DELETE returns 204 and removes the row. James is
    # technology; the target is revenue_cycle (cross-department Admin privilege).
    admin_delete = client.delete(f"/internal-reports/{admin_target.id}", headers=james)
    assert admin_delete.status_code == 204, admin_delete.text
    admin_get = client.get(f"/internal-reports/{admin_target.id}", headers=james)
    assert admin_get.status_code == 404
    assert admin_get.json()["detail"] == "Report not found"
    try:
        internal_report_service.get_report(admin_target.id)
    except InternalReportNotFoundError:
        pass
    else:
        raise AssertionError("deleted report still present in TinyDB")

    me = client.get("/auth/me", headers=james)
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    assert me.json()["department_id"] == "technology"


def test_null_department_does_not_authorize_non_admin_incident_or_supplier_access(
    client: TestClient,
) -> None:
    from datetime import datetime as dt
    from datetime import timezone

    from app.database import get_suppliers_table
    from app.schemas.incident import IncidentCreate
    from app.services import incident_service

    _seed_evaluation_users()
    marcus = _login(client, "marcus.clinical@healthcore.example")
    priya = _login(client, "priya.access@healthcore.example")
    james = _login(client, "james.admin@healthcore.example")

    unassigned_employee = user_service.create_user(
        UserCreate(email="unassigned.employee@healthcore.example", password=SEED_PASSWORD),
        role=UserRole.employee,
    )
    unassigned_supervisor = user_service.create_user(
        UserCreate(email="unassigned.supervisor@healthcore.example", password=SEED_PASSWORD),
        role=UserRole.supervisor,
    )
    assert unassigned_employee.department_id is None
    assert unassigned_supervisor.department_id is None
    unassigned_employee_headers = _login(client, unassigned_employee.email)
    unassigned_supervisor_headers = _login(client, unassigned_supervisor.email)

    tagged = client.post("/api/incidents", json=_INCIDENT_CREATE, headers=marcus)
    assert tagged.status_code == 200, tagged.text
    tagged_incident_id = tagged.json()["id"]
    assert tagged.json()["department_id"] == "clinical_operations"

    untagged_incident = incident_service.create_incident(
        IncidentCreate(**{**_INCIDENT_CREATE, "title": "Untagged incident"}),
        department_id=None,
    )
    assert untagged_incident.department_id is None

    tagged_supplier = client.post(
        "/suppliers",
        json={**_SUPPLIER_CREATE, "name": "Tagged clinical supplier"},
        headers=marcus,
    )
    assert tagged_supplier.status_code == 201, tagged_supplier.text
    tagged_supplier_id = tagged_supplier.json()["id"]
    assert tagged_supplier.json()["department_id"] == "clinical_operations"

    untagged_supplier_id = get_suppliers_table().insert(
        {
            "name": "Untagged supplier",
            "country": "USA",
            "categories": ["medical_supplies"],
            "monthly_rate": 100.0,
            "currency": "USD",
            "status": "active",
            "updated_at": dt.now(timezone.utc).isoformat(),
        }
    )

    marcus_untagged_incident = client.get(
        f"/api/incidents/{untagged_incident.id}", headers=marcus
    )
    assert marcus_untagged_incident.status_code == 403
    assert marcus_untagged_incident.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL
    marcus_incident_list = client.get("/api/incidents", headers=marcus)
    assert marcus_incident_list.status_code == 200
    marcus_incident_ids = {row["id"] for row in marcus_incident_list.json()}
    assert tagged_incident_id in marcus_incident_ids
    assert untagged_incident.id not in marcus_incident_ids

    priya_untagged_incident = client.get(
        f"/api/incidents/{untagged_incident.id}", headers=priya
    )
    assert priya_untagged_incident.status_code == 403
    priya_incident_list = client.get("/api/incidents", headers=priya)
    assert priya_incident_list.status_code == 200
    assert all(row["id"] != untagged_incident.id for row in priya_incident_list.json())

    for headers in (unassigned_employee_headers, unassigned_supervisor_headers):
        untagged_get = client.get(f"/api/incidents/{untagged_incident.id}", headers=headers)
        assert untagged_get.status_code == 403
        assert untagged_get.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL
        tagged_get = client.get(f"/api/incidents/{tagged_incident_id}", headers=headers)
        assert tagged_get.status_code == 403
        listed = client.get("/api/incidents", headers=headers)
        assert listed.status_code == 200
        assert listed.json() == []

    marcus_untagged_supplier = client.get(
        f"/suppliers/{untagged_supplier_id}", headers=marcus
    )
    assert marcus_untagged_supplier.status_code == 403
    assert marcus_untagged_supplier.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL
    marcus_supplier_list = client.get("/suppliers", headers=marcus)
    assert marcus_supplier_list.status_code == 200
    marcus_supplier_ids = {row["id"] for row in marcus_supplier_list.json()}
    assert tagged_supplier_id in marcus_supplier_ids
    assert untagged_supplier_id not in marcus_supplier_ids

    priya_untagged_supplier = client.get(
        f"/suppliers/{untagged_supplier_id}", headers=priya
    )
    assert priya_untagged_supplier.status_code == 403
    priya_supplier_list = client.get("/suppliers", headers=priya)
    assert priya_supplier_list.status_code == 200
    assert all(row["id"] != untagged_supplier_id for row in priya_supplier_list.json())

    for headers in (unassigned_employee_headers, unassigned_supervisor_headers):
        untagged_get = client.get(f"/suppliers/{untagged_supplier_id}", headers=headers)
        assert untagged_get.status_code == 403
        tagged_get = client.get(f"/suppliers/{tagged_supplier_id}", headers=headers)
        assert tagged_get.status_code == 403
        listed = client.get("/suppliers", headers=headers)
        assert listed.status_code == 200
        assert listed.json() == []

    admin_untagged_incident = client.get(
        f"/api/incidents/{untagged_incident.id}", headers=james
    )
    assert admin_untagged_incident.status_code == 200
    assert admin_untagged_incident.json()["department_id"] is None
    admin_incident_list = client.get("/api/incidents", headers=james)
    assert {row["id"] for row in admin_incident_list.json()} >= {
        tagged_incident_id,
        untagged_incident.id,
    }

    admin_untagged_supplier = client.get(
        f"/suppliers/{untagged_supplier_id}", headers=james
    )
    assert admin_untagged_supplier.status_code == 200
    assert admin_untagged_supplier.json().get("department_id") is None
    admin_supplier_list = client.get("/suppliers", headers=james)
    assert {row["id"] for row in admin_supplier_list.json()} >= {
        tagged_supplier_id,
        untagged_supplier_id,
    }

    still_untagged = incident_service.get_incident(untagged_incident.id)
    assert still_untagged.department_id is None
    stored_supplier = get_suppliers_table().get(doc_id=untagged_supplier_id)
    assert stored_supplier is not None
    assert stored_supplier.get("department_id") is None


def test_unassigned_non_admin_cannot_create_inventory_supplier_or_incident(
    client: TestClient,
) -> None:
    """Missing department does not authorize create; assigned users keep own-dept create."""
    from app.database import get_suppliers_table
    from app.services import incident_service

    _seed_evaluation_users()
    priya = _login(client, "priya.access@healthcore.example")
    james = _login(client, "james.admin@healthcore.example")

    unassigned_employee = user_service.create_user(
        UserCreate(email="unassigned.create.employee@healthcore.example", password=SEED_PASSWORD),
        role=UserRole.employee,
    )
    unassigned_supervisor = user_service.create_user(
        UserCreate(email="unassigned.create.supervisor@healthcore.example", password=SEED_PASSWORD),
        role=UserRole.supervisor,
    )
    assert unassigned_employee.department_id is None
    assert unassigned_supervisor.department_id is None
    unassigned_headers = (
        _login(client, unassigned_employee.email),
        _login(client, unassigned_supervisor.email),
    )

    denied_sku = "UNA-CREATE-GAUZE-001"
    denied_supplier_name = "Unassigned create supplier"
    denied_incident_title = "Unassigned create incident"
    product_payload = {
        "name": "Unassigned create gauze",
        "sku": denied_sku,
        "category": "consumables",
        "unit": "box",
        "country": "US",
    }

    products_before = client.get("/inventory/products", headers=james)
    suppliers_before = client.get("/suppliers", headers=james)
    incidents_before = client.get("/api/incidents", headers=james)
    assert products_before.status_code == 200
    assert suppliers_before.status_code == 200
    assert incidents_before.status_code == 200
    product_ids_before = {row["id"] for row in products_before.json()}
    supplier_ids_before = {row["id"] for row in suppliers_before.json()}
    incident_ids_before = {row["id"] for row in incidents_before.json()}

    for headers in unassigned_headers:
        inventory_denied = client.post(
            "/inventory/products",
            json=product_payload,
            headers=headers,
        )
        assert inventory_denied.status_code == 403
        assert inventory_denied.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL

        supplier_denied = client.post(
            "/suppliers",
            json={**_SUPPLIER_CREATE, "name": denied_supplier_name},
            headers=headers,
        )
        assert supplier_denied.status_code == 403
        assert supplier_denied.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL

        incident_denied = client.post(
            "/api/incidents",
            json={**_INCIDENT_CREATE, "title": denied_incident_title},
            headers=headers,
        )
        assert incident_denied.status_code == 403
        assert incident_denied.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL

    products_after_deny = client.get("/inventory/products", headers=james)
    suppliers_after_deny = client.get("/suppliers", headers=james)
    incidents_after_deny = client.get("/api/incidents", headers=james)
    assert products_after_deny.status_code == 200
    assert suppliers_after_deny.status_code == 200
    assert incidents_after_deny.status_code == 200
    assert {row["id"] for row in products_after_deny.json()} == product_ids_before
    assert all(row["sku"] != denied_sku for row in products_after_deny.json())
    assert {row["id"] for row in suppliers_after_deny.json()} == supplier_ids_before
    assert all(row["name"] != denied_supplier_name for row in suppliers_after_deny.json())
    assert {row["id"] for row in incidents_after_deny.json()} == incident_ids_before
    assert all(row["title"] != denied_incident_title for row in incidents_after_deny.json())
    assert all(
        row.get("department_id") is None
        for row in get_suppliers_table().all()
        if row.get("name") == denied_supplier_name
    )
    assert all(
        row.title != denied_incident_title for row in incident_service.list_incidents()
    )

    assigned_product = client.post(
        "/inventory/products",
        json={
            "name": "Patient-experience own-dept gauze",
            "sku": "PE-OWN-CREATE-001",
            "category": "consumables",
            "unit": "box",
            "country": "US",
        },
        headers=priya,
    )
    assigned_supplier = client.post(
        "/suppliers",
        json={**_SUPPLIER_CREATE, "name": "Patient experience own-dept supplier"},
        headers=priya,
    )
    assigned_incident = client.post(
        "/api/incidents",
        json={**_INCIDENT_CREATE, "title": "Patient experience own-dept incident"},
        headers=priya,
    )
    assert assigned_product.status_code == 201, assigned_product.text
    assert assigned_supplier.status_code == 201, assigned_supplier.text
    assert assigned_incident.status_code == 200, assigned_incident.text
    assert assigned_product.json()["department_id"] == "patient_experience"
    assert assigned_supplier.json()["department_id"] == "patient_experience"
    assert assigned_incident.json()["department_id"] == "patient_experience"
    assert assigned_product.json()["sku"] == "PE-OWN-CREATE-001"
    assert assigned_product.json()["id"] not in product_ids_before
    assert assigned_supplier.json()["id"] not in supplier_ids_before
    assert assigned_incident.json()["id"] not in incident_ids_before

    persisted_product = client.get(
        f"/inventory/products/{assigned_product.json()['id']}",
        headers=priya,
    )
    persisted_supplier = client.get(
        f"/suppliers/{assigned_supplier.json()['id']}",
        headers=priya,
    )
    persisted_incident = client.get(
        f"/api/incidents/{assigned_incident.json()['id']}",
        headers=priya,
    )
    assert persisted_product.status_code == 200
    assert persisted_supplier.status_code == 200
    assert persisted_incident.status_code == 200
    assert persisted_product.json()["department_id"] == "patient_experience"
    assert persisted_supplier.json()["department_id"] == "patient_experience"
    assert persisted_incident.json()["department_id"] == "patient_experience"


def test_inventory_missing_department_defaults_without_overwriting_explicit() -> None:
    from sqlalchemy import text
    from sqlmodel import Session, select

    from app.db.database import get_engine, init_databases
    from app.models import MedicalSupply
    from app.services.inventory_seed import ensure_inventory_department_id
    from app.services.inventory_service import get_medical_supply

    isolated_root = Path(os.environ["TINYDB_PATH"]).resolve().parent
    assert "services/api/data" not in isolated_root.as_posix()
    assert os.environ["DATABASE_URL"].startswith("sqlite:///")

    init_databases()
    with Session(get_engine()) as session:
        session.execute(
            text(
                "INSERT INTO medical_supply "
                "(name, sku, category, unit, country, minimum_stock, department_id) "
                "VALUES ('Missing dept gauze', 'MISS-DEPT-001', 'consumables', 'box', 'US', 10, NULL)"
            )
        )
        session.execute(
            text(
                "INSERT INTO medical_supply "
                "(name, sku, category, unit, country, minimum_stock, department_id) "
                "VALUES ('Revenue gauze', 'EXPL-REV-001', 'consumables', 'box', 'US', 10, 'revenue_cycle')"
            )
        )
        session.execute(
            text(
                "INSERT INTO medical_supply "
                "(name, sku, category, unit, country, minimum_stock, department_id) "
                "VALUES ('Legacy gauze', 'UNK-DEPT-001', 'consumables', 'box', 'US', 10, 'legacy_ops')"
            )
        )
        session.commit()
        ensure_inventory_department_id(session)
        ensure_inventory_department_id(session)
        stored = {
            sku: department_id
            for sku, department_id in session.execute(
                text(
                    "SELECT sku, department_id FROM medical_supply "
                    "WHERE sku IN ('MISS-DEPT-001', 'EXPL-REV-001', 'UNK-DEPT-001')"
                )
            )
        }
        assert stored["MISS-DEPT-001"] == "clinical_operations"
        assert stored["EXPL-REV-001"] == "revenue_cycle"
        assert stored["UNK-DEPT-001"] == "legacy_ops"
        missing_supply = session.exec(
            select(MedicalSupply).where(MedicalSupply.sku == "MISS-DEPT-001")
        ).one()
        assert missing_supply.department_id == "clinical_operations"
        public = get_medical_supply(session, missing_supply.id)
        assert public.department_id == missing_supply.department_id


def test_inventory_seed_demo_admin_stamps_clinical_orders_once() -> None:
    from sqlmodel import Session, select

    from app.core.security import verify_password
    from app.db.database import get_engine, init_databases
    from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
    from app.services.inventory_seed import (
        DEMO_ACTOR_EMAIL,
        RETIRED_SEED_LOGIN_EMAIL,
        SEED_CONSUMPTIONS,
        SEED_DELIVERIES,
        SEED_SUPPLIES,
        seed_inventory_if_empty,
        usable_demo_actor_id,
    )

    existing_password = "existing-demo-password-1"
    init_databases()
    created = user_service.create_user(
        UserCreate(email=DEMO_ACTOR_EMAIL, password=existing_password),
        role=UserRole.admin,
        department_id="technology",
    )
    before_id = created.id
    before_hash = created.hashed_password
    with Session(get_engine()) as session:
        first = seed_inventory_if_empty(session)
        second = seed_inventory_if_empty(session)
        supplies = session.exec(select(MedicalSupply)).all()
        deliveries = session.exec(select(SupplyDelivery)).all()
        consumptions = session.exec(select(SupplyConsumption)).all()
    assert first.complete is True
    assert first.message == "Inventory seed complete"
    assert second.complete is True
    assert second.message == "Inventory seed complete"

    after = user_service.get_user_by_email(DEMO_ACTOR_EMAIL)
    assert after is not None
    assert after.id == before_id
    assert after.role == UserRole.admin
    assert after.department_id == "technology"
    if after.hashed_password != before_hash:
        raise AssertionError("demo account credential changed")
    if not verify_password(existing_password, after.hashed_password):
        raise AssertionError("demo account credential no longer matches original password")
    assert usable_demo_actor_id() == before_id
    assert len(supplies) == len(SEED_SUPPLIES)
    assert {row.department_id for row in supplies} == {"clinical_operations"}
    assert len(deliveries) == len(SEED_DELIVERIES)
    assert len(consumptions) == len(SEED_CONSUMPTIONS)
    assert {row.user_uuid for row in deliveries} == {before_id}
    assert {row.user_uuid for row in consumptions} == {before_id}
    assert user_service.get_user_by_email(RETIRED_SEED_LOGIN_EMAIL) is None


def test_inventory_seed_catalog_without_orders_completes_when_demo_admin_exists() -> None:
    from sqlmodel import Session, select

    from app.db.database import get_engine, init_databases
    from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
    from app.services.inventory_seed import (
        DEMO_ACTOR_EMAIL,
        RETIRED_SEED_LOGIN_EMAIL,
        SEED_CONSUMPTIONS,
        SEED_DELIVERIES,
        seed_inventory_if_empty,
    )

    init_databases()
    with Session(get_engine()) as session:
        pending = seed_inventory_if_empty(session)
        still_pending = seed_inventory_if_empty(session)
        assert len(session.exec(select(MedicalSupply)).all()) == 6
        assert session.exec(select(SupplyDelivery)).all() == []
        assert session.exec(select(SupplyConsumption)).all() == []
    assert pending.complete is False
    assert pending.message.startswith("Inventory seed pending:")
    assert pending.missing_delivery_count == 4
    assert pending.missing_consumption_count == 3
    assert still_pending.complete is False

    created = user_service.create_user(
        UserCreate(email=DEMO_ACTOR_EMAIL, password="existing-demo-password-1"),
        role=UserRole.admin,
        department_id="technology",
    )
    with Session(get_engine()) as session:
        completed = seed_inventory_if_empty(session)
        again = seed_inventory_if_empty(session)
        deliveries = session.exec(select(SupplyDelivery)).all()
        consumptions = session.exec(select(SupplyConsumption)).all()
    assert completed.complete is True
    assert completed.message == "Inventory seed complete"
    assert again.complete is True

    assert len(deliveries) == len(SEED_DELIVERIES)
    assert len(consumptions) == len(SEED_CONSUMPTIONS)
    assert {row.user_uuid for row in deliveries} == {created.id}
    assert {row.user_uuid for row in consumptions} == {created.id}
    assert user_service.get_user_by_email(RETIRED_SEED_LOGIN_EMAIL) is None


def test_inventory_seed_missing_inactive_unauthorized_and_duplicate_actors_do_not_complete() -> None:
    from datetime import UTC, datetime

    from sqlmodel import Session, select
    from tinydb import Query

    from app.core.security import hash_password
    from app.db.database import get_engine, init_databases
    from app.db.tinydb import users_table
    from app.models import SupplyConsumption, SupplyDelivery
    from app.schemas.user import UserUpdate
    from app.services.inventory_seed import (
        DEMO_ACTOR_EMAIL,
        RETIRED_SEED_LOGIN_EMAIL,
        seed_inventory_if_empty,
        usable_demo_actor_id,
    )

    init_databases()
    assert usable_demo_actor_id() is None
    with Session(get_engine()) as session:
        pending = seed_inventory_if_empty(session)
        assert session.exec(select(SupplyDelivery)).all() == []
        assert session.exec(select(SupplyConsumption)).all() == []
    assert pending.complete is False
    assert pending.message.startswith("Inventory seed pending:")
    assert "approved demo actor unavailable" in (pending.pending_reason or "")
    assert pending.missing_delivery_count == 4
    assert pending.missing_consumption_count == 3

    employee = user_service.create_user(
        UserCreate(email=DEMO_ACTOR_EMAIL, password="existing-demo-password-1"),
        role=UserRole.employee,
        department_id="technology",
    )
    before_employee = users_table().get(Query().id == employee.id)
    with Session(get_engine()) as session:
        seed_inventory_if_empty(session)
        assert session.exec(select(SupplyDelivery)).all() == []
        assert session.exec(select(SupplyConsumption)).all() == []
    after_employee = users_table().get(Query().id == employee.id)
    assert after_employee == before_employee
    assert after_employee["role"] == "employee"

    user_service.update_user(
        employee.id,
        UserUpdate(role=UserRole.admin, department_id="technology", is_active=False),
    )
    inactive = users_table().get(Query().id == employee.id)
    with Session(get_engine()) as session:
        seed_inventory_if_empty(session)
        assert session.exec(select(SupplyDelivery)).all() == []
    assert users_table().get(Query().id == employee.id) == inactive
    assert inactive["is_active"] is False

    users_table().remove(Query().email == DEMO_ACTOR_EMAIL)
    users_table().insert(
        {
            "id": "dup-one",
            "email": DEMO_ACTOR_EMAIL,
            "hashed_password": hash_password("existing-demo-password-1"),
            "is_active": True,
            "role": "admin",
            "role_id": "admin",
            "department_id": "technology",
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    users_table().insert(
        {
            "id": "dup-two",
            "email": "Orders.QuoteFlow@gmail.com",
            "hashed_password": hash_password("existing-demo-password-1"),
            "is_active": True,
            "role": "admin",
            "role_id": "admin",
            "department_id": "technology",
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    assert usable_demo_actor_id() is None
    with Session(get_engine()) as session:
        seed_inventory_if_empty(session)
        assert session.exec(select(SupplyDelivery)).all() == []
        assert session.exec(select(SupplyConsumption)).all() == []
    assert user_service.get_user_by_email(RETIRED_SEED_LOGIN_EMAIL) is None


def test_inventory_seed_retired_login_is_never_created_or_used() -> None:
    from sqlmodel import Session, select

    from app.core.security import verify_password
    from app.db.database import get_engine, init_databases
    from app.models import SupplyDelivery
    from app.services.inventory_seed import (
        RETIRED_SEED_LOGIN_EMAIL,
        seed_inventory_if_empty,
        usable_demo_actor_id,
    )

    existing_password = "existing-seed-password-1"
    init_databases()
    retired = user_service.create_user(
        UserCreate(email=RETIRED_SEED_LOGIN_EMAIL, password=existing_password),
        role=UserRole.admin,
        department_id="technology",
    )
    before_hash = retired.hashed_password
    with Session(get_engine()) as session:
        seed_inventory_if_empty(session)
        seed_inventory_if_empty(session)
        deliveries = session.exec(select(SupplyDelivery)).all()

    after = user_service.get_user_by_email(RETIRED_SEED_LOGIN_EMAIL)
    assert after is not None
    assert after.id == retired.id
    if after.hashed_password != before_hash:
        raise AssertionError("retired login credential changed")
    if not verify_password(existing_password, after.hashed_password):
        raise AssertionError("retired login credential no longer matches original password")
    assert usable_demo_actor_id() is None
    assert deliveries == []


def test_inventory_seed_preserves_existing_order_user_uuid_without_account() -> None:
    from datetime import UTC, datetime

    from sqlalchemy import text
    from sqlmodel import Session

    from app.db.database import get_engine, init_databases
    from app.services.inventory_seed import (
        DEMO_ACTOR_EMAIL,
        RETIRED_SEED_LOGIN_EMAIL,
        seed_inventory_if_empty,
    )

    isolated_root = Path(os.environ["TINYDB_PATH"]).resolve().parent
    assert "services/api/data" not in isolated_root.as_posix()
    assert os.environ["DATABASE_URL"].startswith("sqlite:///")

    preserved_actor = "existing-order-actor-uuid"
    stamped_at = datetime.now(UTC).isoformat()
    init_databases()
    assert user_service.get_user_by_email(RETIRED_SEED_LOGIN_EMAIL) is None
    assert user_service.get_user_by_email(DEMO_ACTOR_EMAIL) is None
    with Session(get_engine()) as session:
        session.execute(
            text(
                "INSERT INTO medical_supply "
                "(name, sku, category, unit, country, minimum_stock, department_id) "
                "VALUES ('Owned gauze', 'OWN-DEPT-001', 'consumables', 'box', 'US', 10, 'revenue_cycle')"
            )
        )
        session.execute(
            text(
                "INSERT INTO supply_delivery "
                "(supply_id, quantity, vendor_name, clinic_id, created_at, user_uuid) "
                "VALUES (1, 8, 'Existing Vendor', 1, :created_at, :actor)"
            ),
            {"actor": preserved_actor, "created_at": stamped_at},
        )
        session.execute(
            text(
                "INSERT INTO supply_consumption "
                "(supply_id, quantity, consumption_type, department, clinic_id, created_at, user_uuid) "
                "VALUES (1, 2, 'clinical_use', 'primary_care', 1, :created_at, :actor)"
            ),
            {"actor": preserved_actor, "created_at": stamped_at},
        )
        session.commit()
        result = seed_inventory_if_empty(session)
        seed_inventory_if_empty(session)
        catalog = list(
            session.execute(text("SELECT sku, department_id FROM medical_supply"))
        )
        delivery_actors = [
            row[0] for row in session.execute(text("SELECT user_uuid FROM supply_delivery"))
        ]
        consumption_actors = [
            row[0]
            for row in session.execute(text("SELECT user_uuid FROM supply_consumption"))
        ]

    assert catalog == [("OWN-DEPT-001", "revenue_cycle")]
    assert delivery_actors == [preserved_actor]
    assert consumption_actors == [preserved_actor]
    assert result.complete is False
    assert result.message.startswith("Inventory seed pending:")
    assert "Inventory seed complete" not in result.message
    assert result.missing_delivery_count == 4
    assert result.missing_consumption_count == 3
    assert "HCR-PPE-001" in result.missing_products
    assert user_service.get_user_by_email(RETIRED_SEED_LOGIN_EMAIL) is None
    assert user_service.get_user_by_email(DEMO_ACTOR_EMAIL) is None


def test_inventory_seed_no_actor_does_not_block_later_admin_user_create() -> None:
    from sqlmodel import Session, select

    from app.db.database import get_engine, init_databases
    from app.models import SupplyDelivery
    from app.services.inventory_seed import (
        DEMO_ACTOR_EMAIL,
        RETIRED_SEED_LOGIN_EMAIL,
        seed_inventory_if_empty,
    )

    init_databases()
    with Session(get_engine()) as session:
        seed_inventory_if_empty(session)
    assert user_service.get_user_by_email(RETIRED_SEED_LOGIN_EMAIL) is None
    created = user_service.create_user(
        UserCreate(email=DEMO_ACTOR_EMAIL, password="existing-demo-password-1"),
        role=UserRole.admin,
        department_id="technology",
    )
    with Session(get_engine()) as session:
        seed_inventory_if_empty(session)
        deliveries = session.exec(select(SupplyDelivery)).all()
    assert {row.user_uuid for row in deliveries} == {created.id}


def test_demo_admin_can_create_clinical_orders_and_technology_staff_cannot(
    client: TestClient,
) -> None:
    from app.services.inventory_seed import DEMO_ACTOR_EMAIL

    demo_user = user_service.create_user(
        UserCreate(email=DEMO_ACTOR_EMAIL, password=SEED_PASSWORD),
        role=UserRole.admin,
        department_id="technology",
    )
    user_service.create_user(
        UserCreate(email="tech.employee@healthcore.example", password=SEED_PASSWORD),
        role=UserRole.employee,
        department_id="technology",
    )
    user_service.create_user(
        UserCreate(email="tech.supervisor@healthcore.example", password=SEED_PASSWORD),
        role=UserRole.supervisor,
        department_id="technology",
    )
    demo = _login(client, DEMO_ACTOR_EMAIL)
    employee = _login(client, "tech.employee@healthcore.example")
    supervisor = _login(client, "tech.supervisor@healthcore.example")

    catalog = client.get("/inventory/products", headers=demo)
    assert catalog.status_code == 200, catalog.text
    clinical = next(row for row in catalog.json() if row["department_id"] == "clinical_operations")
    payload = {
        "supply_id": clinical["id"],
        "quantity": 2,
        "vendor_name": "Demo clinical inbound",
        "clinic_id": 1,
    }
    employee_denied = client.post("/inventory/orders/inbound", json=payload, headers=employee)
    supervisor_denied = client.post("/inventory/orders/inbound", json=payload, headers=supervisor)
    assert employee_denied.status_code == 403
    assert employee_denied.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL
    assert supervisor_denied.status_code == 403
    assert supervisor_denied.json()["detail"] == INSUFFICIENT_DEPARTMENT_DETAIL
    created = client.post("/inventory/orders/inbound", json=payload, headers=demo)
    assert created.status_code == 201, created.text
    assert created.json()["vendor_name"] == "Demo clinical inbound"
    me = client.get("/auth/me", headers=demo)
    assert me.status_code == 200
    assert me.json()["email"] == DEMO_ACTOR_EMAIL
    assert me.json()["role"] == "admin"
    assert me.json()["department_id"] == "technology"
    assert created.json()["user_uuid"] == demo_user.id


def _load_seed_inventory_command():
    import importlib.util

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "seed_inventory.py"
    spec = importlib.util.spec_from_file_location("seed_inventory_command", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _insert_prescribed_catalog(session) -> None:
    from datetime import date

    from app.models import MedicalSupply
    from app.services.inventory_seed import CATALOG_DEPARTMENT_ID, SEED_SUPPLIES

    for row in SEED_SUPPLIES:
        expiry = row["expiry_date"] if isinstance(row["expiry_date"], date) else None
        session.add(
            MedicalSupply(
                name=str(row["name"]),
                sku=str(row["sku"]),
                category=str(row["category"]),
                unit=str(row["unit"]),
                country=str(row["country"]),
                minimum_stock=int(row["minimum_stock"]),
                expiry_date=expiry,
                department_id=CATALOG_DEPARTMENT_ID,
            )
        )
    session.commit()


def test_inventory_seed_partial_catalog_does_not_satisfy_required_orders() -> None:
    from sqlmodel import Session, select

    from app.db.database import get_engine, init_databases
    from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
    from app.services.inventory_seed import (
        CATALOG_DEPARTMENT_ID,
        SEED_CONSUMPTIONS,
        SEED_DELIVERIES,
        SEED_SUPPLIES,
        seed_inventory_if_empty,
    )

    prescribed = next(row for row in SEED_SUPPLIES if row["sku"] == "HCR-PPE-001")
    init_databases()
    with Session(get_engine()) as session:
        session.add(
            MedicalSupply(
                name=str(prescribed["name"]),
                sku=str(prescribed["sku"]),
                category=str(prescribed["category"]),
                unit=str(prescribed["unit"]),
                country=str(prescribed["country"]),
                minimum_stock=int(prescribed["minimum_stock"]),
                expiry_date=prescribed["expiry_date"],
                department_id=CATALOG_DEPARTMENT_ID,
            )
        )
        session.commit()
        result = seed_inventory_if_empty(session)
        skus = [row.sku for row in session.exec(select(MedicalSupply)).all()]
        deliveries = session.exec(select(SupplyDelivery)).all()
        consumptions = session.exec(select(SupplyConsumption)).all()

    assert skus == ["HCR-PPE-001"]
    assert deliveries == []
    assert consumptions == []
    assert result.complete is False
    assert result.message.startswith("Inventory seed pending:")
    assert "Inventory seed complete" not in result.message
    assert "required products absent" in (result.pending_reason or "")
    assert "HCR-DIAG-001" in result.missing_products
    assert result.missing_delivery_count == len(SEED_DELIVERIES)
    assert result.missing_consumption_count == len(SEED_CONSUMPTIONS)


def test_inventory_seed_nonempty_unrelated_catalog_does_not_satisfy_required_orders() -> None:
    from sqlalchemy import text
    from sqlmodel import Session, select

    from app.db.database import get_engine, init_databases
    from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
    from app.services.inventory_seed import (
        SEED_CONSUMPTIONS,
        SEED_DELIVERIES,
        SEED_SUPPLIES,
        seed_inventory_if_empty,
    )

    init_databases()
    with Session(get_engine()) as session:
        session.execute(
            text(
                "INSERT INTO medical_supply "
                "(name, sku, category, unit, country, minimum_stock, department_id) "
                "VALUES ('Owned gauze', 'OWN-DEPT-001', 'consumables', 'box', 'US', 10, 'revenue_cycle')"
            )
        )
        session.commit()
        result = seed_inventory_if_empty(session)
        catalog = list(session.execute(text("SELECT sku, department_id FROM medical_supply")))
        deliveries = session.exec(select(SupplyDelivery)).all()
        consumptions = session.exec(select(SupplyConsumption)).all()

    assert catalog == [("OWN-DEPT-001", "revenue_cycle")]
    assert deliveries == []
    assert consumptions == []
    assert result.complete is False
    assert result.message.startswith("Inventory seed pending:")
    assert "Inventory seed complete" not in result.message
    assert result.missing_products == tuple(str(row["sku"]) for row in SEED_SUPPLIES)
    assert result.missing_delivery_count == len(SEED_DELIVERIES)
    assert result.missing_consumption_count == len(SEED_CONSUMPTIONS)


def test_inventory_seed_complete_historical_tuples_do_not_require_actor() -> None:
    from sqlmodel import Session, select

    from app.db.database import get_engine, init_databases
    from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
    from app.services.inventory_seed import (
        DEMO_ACTOR_EMAIL,
        SEED_CONSUMPTIONS,
        SEED_DELIVERIES,
        seed_inventory_if_empty,
        usable_demo_actor_id,
    )

    historical_owner = "historical-seed-owner-uuid"
    init_databases()
    assert usable_demo_actor_id() is None
    assert user_service.get_user_by_email(DEMO_ACTOR_EMAIL) is None
    with Session(get_engine()) as session:
        _insert_prescribed_catalog(session)
        supplies = {row.sku: row for row in session.exec(select(MedicalSupply)).all()}
        for sku, quantity, vendor_name, clinic_id in SEED_DELIVERIES:
            session.add(
                SupplyDelivery(
                    supply_id=supplies[sku].id,
                    quantity=quantity,
                    vendor_name=vendor_name,
                    clinic_id=clinic_id,
                    user_uuid=historical_owner,
                )
            )
        for sku, quantity, consumption_type, clinic_id, department in SEED_CONSUMPTIONS:
            session.add(
                SupplyConsumption(
                    supply_id=supplies[sku].id,
                    quantity=quantity,
                    consumption_type=consumption_type,
                    department=department,
                    clinic_id=clinic_id,
                    user_uuid=historical_owner,
                )
            )
        session.commit()
        result = seed_inventory_if_empty(session)
        delivery_owners = {row.user_uuid for row in session.exec(select(SupplyDelivery)).all()}
        consumption_owners = {
            row.user_uuid for row in session.exec(select(SupplyConsumption)).all()
        }

    assert result.complete is True
    assert result.message == "Inventory seed complete"
    assert result.missing_delivery_count == 0
    assert result.missing_consumption_count == 0
    assert delivery_owners == {historical_owner}
    assert consumption_owners == {historical_owner}
    assert usable_demo_actor_id() is None
    assert user_service.get_user_by_email(DEMO_ACTOR_EMAIL) is None


def test_seed_inventory_command_reports_complete_only_when_required_records_exist(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from sqlmodel import Session, select

    from app.db.database import get_engine, init_databases
    from app.models import SupplyConsumption, SupplyDelivery
    from app.services.inventory_seed import (
        DEMO_ACTOR_EMAIL,
        SEED_CONSUMPTIONS,
        SEED_DELIVERIES,
    )

    init_databases()
    user_service.create_user(
        UserCreate(email=DEMO_ACTOR_EMAIL, password="existing-demo-password-1"),
        role=UserRole.admin,
        department_id="technology",
    )
    command = _load_seed_inventory_command()
    exit_code = command.main()
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "Inventory seed complete"
    assert "Inventory seed pending" not in captured.out
    with Session(get_engine()) as session:
        assert len(session.exec(select(SupplyDelivery)).all()) == len(SEED_DELIVERIES)
        assert len(session.exec(select(SupplyConsumption)).all()) == len(SEED_CONSUMPTIONS)


def test_seed_inventory_command_reports_pending_when_required_work_remains(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from sqlmodel import Session, select

    from app.db.database import get_engine, init_databases
    from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
    from app.services.inventory_seed import SEED_SUPPLIES

    init_databases()
    command = _load_seed_inventory_command()
    exit_code = command.main()
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out.strip().startswith("Inventory seed pending:")
    assert "Inventory seed complete" not in captured.out
    with Session(get_engine()) as session:
        assert len(session.exec(select(MedicalSupply)).all()) == len(SEED_SUPPLIES)
        assert session.exec(select(SupplyDelivery)).all() == []
        assert session.exec(select(SupplyConsumption)).all() == []


def test_inventory_seed_insufficient_stock_backfill_does_not_persist_or_complete() -> None:
    from datetime import UTC, datetime

    from sqlmodel import Session, select

    from app.db.database import get_engine, init_databases
    from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
    from app.services.inventory_seed import (
        DEMO_ACTOR_EMAIL,
        PENDING_STOCK,
        SEED_CONSUMPTIONS,
        SEED_DELIVERIES,
        seed_inventory_if_empty,
    )
    from app.services.inventory_service import computed_stock_for_supply

    historical_owner = "historical-delivery-owner-uuid"
    extra_owner = "preexisting-consumption-owner-uuid"
    stamped_at = datetime.now(UTC)
    init_databases()
    created = user_service.create_user(
        UserCreate(email=DEMO_ACTOR_EMAIL, password="existing-demo-password-1"),
        role=UserRole.admin,
        department_id="technology",
    )
    with Session(get_engine()) as session:
        _insert_prescribed_catalog(session)
        supplies = {row.sku: row for row in session.exec(select(MedicalSupply)).all()}
        for sku, quantity, vendor_name, clinic_id in SEED_DELIVERIES:
            session.add(
                SupplyDelivery(
                    supply_id=supplies[sku].id,
                    quantity=quantity,
                    vendor_name=vendor_name,
                    clinic_id=clinic_id,
                    user_uuid=historical_owner,
                    created_at=stamped_at,
                )
            )
        ppe = supplies["HCR-PPE-001"]
        session.add(
            SupplyConsumption(
                supply_id=ppe.id,
                quantity=115,
                consumption_type="clinical_use",
                department="primary_care",
                clinic_id=2,
                user_uuid=extra_owner,
                created_at=stamped_at,
            )
        )
        session.commit()
        available_before = computed_stock_for_supply(session, ppe.id)
        result = seed_inventory_if_empty(session)
        deliveries = session.exec(select(SupplyDelivery)).all()
        consumptions = session.exec(select(SupplyConsumption)).all()
        available_after = computed_stock_for_supply(session, ppe.id)

    assert available_before == 5
    assert available_after == 5
    assert result.complete is False
    assert result.pending_reason == PENDING_STOCK
    assert result.message.startswith("Inventory seed pending:")
    assert "Inventory seed complete" not in result.message
    assert result.missing_consumption_count == len(SEED_CONSUMPTIONS)
    assert len(deliveries) == len(SEED_DELIVERIES)
    assert {row.user_uuid for row in deliveries} == {historical_owner}
    assert len(consumptions) == 1
    assert consumptions[0].quantity == 115
    assert consumptions[0].user_uuid == extra_owner
    assert created.id not in {row.user_uuid for row in consumptions}


def test_inventory_seed_valid_partial_history_backfill_preserves_owners() -> None:
    from sqlmodel import Session, select

    from app.db.database import get_engine, init_databases
    from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
    from app.services.inventory_seed import (
        DEMO_ACTOR_EMAIL,
        SEED_CONSUMPTIONS,
        SEED_DELIVERIES,
        seed_inventory_if_empty,
    )

    historical_owner = "historical-delivery-owner-uuid"
    init_databases()
    created = user_service.create_user(
        UserCreate(email=DEMO_ACTOR_EMAIL, password="existing-demo-password-1"),
        role=UserRole.admin,
        department_id="technology",
    )
    with Session(get_engine()) as session:
        _insert_prescribed_catalog(session)
        supplies = {row.sku: row for row in session.exec(select(MedicalSupply)).all()}
        for sku, quantity, vendor_name, clinic_id in SEED_DELIVERIES:
            session.add(
                SupplyDelivery(
                    supply_id=supplies[sku].id,
                    quantity=quantity,
                    vendor_name=vendor_name,
                    clinic_id=clinic_id,
                    user_uuid=historical_owner,
                )
            )
        session.commit()
        result = seed_inventory_if_empty(session)
        deliveries = session.exec(select(SupplyDelivery)).all()
        consumptions = session.exec(select(SupplyConsumption)).all()

    assert result.complete is True
    assert result.message == "Inventory seed complete"
    assert len(deliveries) == len(SEED_DELIVERIES)
    assert len(consumptions) == len(SEED_CONSUMPTIONS)
    assert {row.user_uuid for row in deliveries} == {historical_owner}
    assert {row.user_uuid for row in consumptions} == {created.id}


def test_consumption_stock_rule_rejects_quantity_above_available() -> None:
    from datetime import UTC, datetime

    from sqlmodel import Session, select

    from app.db.database import get_engine, init_databases
    from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery
    from app.schemas.inventory import SupplyConsumptionCreate
    from app.schemas.user import UserInDB
    from app.services.inventory_service import (
        InsufficientSupplyStockError,
        assert_consumption_within_stock,
        computed_stock_for_supply,
        create_supply_consumption,
    )

    init_databases()
    with Session(get_engine()) as session:
        supply = MedicalSupply(
            name="Nitrile gloves (box of 100)",
            sku="HCR-PPE-001",
            category="ppe",
            unit="box",
            country="US",
            minimum_stock=10,
            department_id="clinical_operations",
        )
        session.add(supply)
        session.commit()
        session.refresh(supply)
        session.add(
            SupplyDelivery(
                supply_id=supply.id,
                quantity=10,
                vendor_name="MedLine Industries",
                clinic_id=1,
                user_uuid="stock-rule-owner",
                created_at=datetime.now(UTC),
            )
        )
        session.commit()
        assert computed_stock_for_supply(session, supply.id) == 10
        assert_consumption_within_stock(session, supply, 10)
        with pytest.raises(InsufficientSupplyStockError) as blocked:
            assert_consumption_within_stock(session, supply, 11)
        assert blocked.value.available == 10
        assert blocked.value.requested == 11
        actor = UserInDB(
            id="stock-rule-owner",
            email="stock.rule@healthcore.com",
            is_active=True,
            role=UserRole.admin,
            department_id="technology",
            created_at=datetime.now(UTC),
            hashed_password="not-used",
        )
        with pytest.raises(InsufficientSupplyStockError):
            create_supply_consumption(
                session,
                SupplyConsumptionCreate(
                    supply_id=supply.id,
                    quantity=11,
                    consumption_type="clinical_use",
                    department="primary_care",
                    clinic_id=1,
                ),
                actor,
            )
        assert session.exec(select(SupplyConsumption)).all() == []
        created = create_supply_consumption(
            session,
            SupplyConsumptionCreate(
                supply_id=supply.id,
                quantity=10,
                consumption_type="clinical_use",
                department="primary_care",
                clinic_id=1,
            ),
            actor,
        )
        assert created.quantity == 10
        assert computed_stock_for_supply(session, supply.id) == 0
