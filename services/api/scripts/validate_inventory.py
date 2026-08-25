"""Inventory milestone validation against the HealthCore CONTEXT entities."""

from __future__ import annotations

import inspect
import os
import sys
import tempfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

_tmpdir = tempfile.mkdtemp(prefix="inventory-")
_sqlite_path = (Path(_tmpdir) / "inventory.db").resolve().as_posix()
os.environ["SECRET_KEY"] = "validation-secret-key-32chars!!"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["TINYDB_PATH"] = str(Path(_tmpdir) / "auth.json")
os.environ["DATABASE_URL"] = f"sqlite:///{_sqlite_path}"

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import get_db, get_engine, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from app.models import MedicalSupply, SupplyConsumption, SupplyDelivery  # noqa: E402
from app.services.inventory_seed import (  # noqa: E402
    SEED_CONSUMPTIONS,
    SEED_DELIVERIES,
    SEED_SUPPLIES,
    expected_seed_stock,
    seed_inventory_if_empty,
)
from app.services.inventory_service import INSUFFICIENT_STOCK_TEMPLATE  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()
reset_engine_for_tests()

REQUIRED_SKUS = (
    "HCR-PPE-001",
    "HCR-PPE-002",
    "HCR-WND-001",
    "HCR-DIAG-001",
    "HCR-DIAG-002",
    "HCR-MED-001",
)


def _auth_header(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": password})
    token = response.json().get("access_token")
    if response.status_code != 200 or not token:
        raise RuntimeError(f"login failed for {email}: {response.status_code} {response.text}")
    return {"Authorization": f"Bearer {token}"}


def main() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"PASS  {name}")
        else:
            failures.append(name)
            print(f"FAIL  {name} {detail}")

    settings = get_settings()
    check("DATABASE_URL from environment", settings.database_url.startswith("sqlite:///"))
    check("TinyDB path from environment", Path(settings.tinydb_path).name == "auth.json")
    check(
        "no SQLModel User table",
        "User" not in SQLModel.metadata.tables and "user" not in SQLModel.metadata.tables,
        str(list(SQLModel.metadata.tables)),
    )
    check(
        "ORM tables are MedicalSupply/SupplyDelivery/SupplyConsumption",
        set(SQLModel.metadata.tables) == {"medical_supply", "supply_delivery", "supply_consumption"}
        or {"medical_supply", "supply_delivery", "supply_consumption"}.issubset(SQLModel.metadata.tables),
        str(list(SQLModel.metadata.tables)),
    )

    with TestClient(app) as client:
        r = client.get("/health")
        check("GET /health public", r.status_code == 200 and r.json()["status"] == "ok")

        r = client.get("/inventory/products")
        check("GET /inventory/products without token -> 401", r.status_code == 401)
        r = client.get("/inventory/products/1")
        check("GET /inventory/products/{id} without token -> 401", r.status_code == 401)
        r = client.get("/inventory/orders")
        check("GET /inventory/orders without token -> 401", r.status_code == 401)
        r = client.post(
            "/inventory/products",
            json={
                "name": "Should fail",
                "sku": "HCR-FAIL",
                "category": "ppe",
                "unit": "box",
                "country": "US",
            },
        )
        check("POST /inventory/products without token -> 401", r.status_code == 401)
        r = client.post(
            "/inventory/orders/inbound",
            json={"supply_id": 1, "quantity": 1, "vendor_name": "MedLine Industries", "clinic_id": 1},
        )
        check("POST /inventory/orders/inbound without token -> 401", r.status_code == 401)
        r = client.post(
            "/inventory/orders/outbound",
            json={"supply_id": 1, "quantity": 1, "consumption_type": "clinical_use", "clinic_id": 1},
        )
        check("POST /inventory/orders/outbound without token -> 401", r.status_code == 401)

        r = client.post(
            "/users",
            json={"email": "clinician@healthcore.com", "password": "SecurePass1!", "name": "Clinician"},
        )
        check("register clinician", r.status_code == 201, r.text)
        clinician = r.json() if r.status_code == 201 else {}
        auth = _auth_header(client, "clinician@healthcore.com", "SecurePass1!")

        r = client.get("/inventory/products", headers=auth)
        check("GET /inventory/products authenticated", r.status_code == 200, r.text)
        products = r.json() if r.status_code == 200 else []
        check("seeded six MedicalSupply records", len(products) == len(SEED_SUPPLIES), str(len(products)))
        skus = {row["sku"] for row in products}
        check("exact required seed SKUs", skus == set(REQUIRED_SKUS), str(skus))

        required_fields = {"id", "name", "sku", "category", "unit", "country", "current_stock"}
        check(
            "MedicalSupply responses use required fields including country",
            all(required_fields <= set(row) for row in products),
            str(products[:1]),
        )
        check(
            "current_stock is present and stock is not a stored field",
            all("current_stock" in row and "stock" not in row for row in products),
        )

        expected = expected_seed_stock()
        stock_by_sku = {row["sku"]: row["current_stock"] for row in products}
        check(
            "seeded current_stock equals deliveries minus consumptions",
            stock_by_sku == expected,
            f"got={stock_by_sku} expected={expected}",
        )

        gloves = next((row for row in products if row["sku"] == "HCR-PPE-001"), None)
        check("HCR-PPE-001 present", gloves is not None)
        if gloves:
            r = client.get(f"/inventory/products/{gloves['id']}", headers=auth)
            check(
                "GET /inventory/products/{id}",
                r.status_code == 200 and r.json()["current_stock"] == expected["HCR-PPE-001"],
                r.text,
            )

        r = client.post(
            "/inventory/products",
            headers=auth,
            json={
                "name": "Alcohol prep pads",
                "sku": "HCR-CON-001",
                "category": "consumables",
                "unit": "box",
                "country": "US",
            },
        )
        check("POST /inventory/products authenticated -> 201", r.status_code == 201, r.text)
        created = r.json() if r.status_code == 201 else {}
        check("new MedicalSupply current_stock is 0", created.get("current_stock") == 0, str(created))
        check("new MedicalSupply has country", created.get("country") == "US", str(created))

        r = client.post(
            "/inventory/products",
            headers=auth,
            json={
                "name": "Invalid country",
                "sku": "HCR-BAD-COUNTRY",
                "category": "ppe",
                "unit": "box",
                "country": "CA",
            },
        )
        check("invalid country rejected by request schema", r.status_code == 422, r.text)

        r = client.post(
            "/inventory/orders/inbound",
            headers=auth,
            json={
                "supply_id": created.get("id"),
                "quantity": 10,
                "vendor_name": "MedLine Industries",
                "clinic_id": 3,
            },
        )
        check("POST /inventory/orders/inbound authenticated -> 201", r.status_code == 201, r.text)
        delivery = r.json() if r.status_code == 201 else {}
        check("delivery stores TinyDB user_uuid", delivery.get("user_uuid") == clinician.get("id"), str(delivery))
        check("delivery uses supply_id", delivery.get("supply_id") == created.get("id"), str(delivery))
        check("delivery has vendor_name and clinic_id", delivery.get("vendor_name") == "MedLine Industries" and delivery.get("clinic_id") == 3, str(delivery))
        check("delivery ignores caller-provided user_uuid", "user_uuid" not in {
            "supply_id": created.get("id"),
            "quantity": 10,
            "vendor_name": "MedLine Industries",
            "clinic_id": 3,
        })

        r = client.post(
            "/inventory/orders/inbound",
            headers=auth,
            json={
                "supply_id": created.get("id"),
                "quantity": 2,
                "vendor_name": "Bound Tree Medical",
                "clinic_id": 3,
                "user_uuid": "forged-uuid",
            },
        )
        check(
            "caller-provided user_uuid is ignored",
            r.status_code == 201 and r.json().get("user_uuid") == clinician.get("id"),
            r.text,
        )

        r = client.get(f"/inventory/products/{created.get('id')}", headers=auth)
        check("stock after deliveries 10+2 is 12", r.status_code == 200 and r.json().get("current_stock") == 12, r.text)

        r = client.post(
            "/inventory/orders/inbound",
            headers=auth,
            json={"supply_id": created.get("id"), "quantity": 1, "vendor_name": "MedLine Industries", "clinic_id": 0},
        )
        check("clinic_id below 1 rejected", r.status_code == 422, r.text)
        r = client.post(
            "/inventory/orders/inbound",
            headers=auth,
            json={"supply_id": created.get("id"), "quantity": 1, "vendor_name": "MedLine Industries", "clinic_id": 13},
        )
        check("clinic_id above 12 rejected", r.status_code == 422, r.text)
        r = client.post(
            "/inventory/orders/inbound",
            headers=auth,
            json={"supply_id": created.get("id"), "quantity": 0, "vendor_name": "MedLine Industries", "clinic_id": 1},
        )
        check("zero delivery quantity rejected", r.status_code == 422, r.text)
        r = client.post(
            "/inventory/orders/inbound",
            headers=auth,
            json={"supply_id": created.get("id"), "quantity": -1, "vendor_name": "MedLine Industries", "clinic_id": 1},
        )
        check("negative delivery quantity rejected", r.status_code == 422, r.text)

        r = client.post(
            "/inventory/orders/outbound",
            headers=auth,
            json={
                "supply_id": created.get("id"),
                "quantity": 4,
                "consumption_type": "clinical_use",
                "clinic_id": 3,
            },
        )
        check("POST /inventory/orders/outbound authenticated -> 201", r.status_code == 201, r.text)
        consumption = r.json() if r.status_code == 201 else {}
        check("consumption stores TinyDB user_uuid", consumption.get("user_uuid") == clinician.get("id"), str(consumption))
        check("consumption uses supply_id and consumption_type", consumption.get("supply_id") == created.get("id") and consumption.get("consumption_type") == "clinical_use", str(consumption))

        r = client.get(f"/inventory/products/{created.get('id')}", headers=auth)
        check("stock after consumption 4 is 8", r.status_code == 200 and r.json().get("current_stock") == 8, r.text)

        r = client.post(
            "/inventory/orders/outbound",
            headers=auth,
            json={
                "supply_id": created.get("id"),
                "quantity": 1,
                "consumption_type": "discarded",
                "clinic_id": 3,
            },
        )
        check("invalid consumption_type rejected by request schema", r.status_code == 422, r.text)

        r = client.post(
            "/inventory/orders/outbound",
            headers=auth,
            json={
                "supply_id": created.get("id"),
                "quantity": 0,
                "consumption_type": "clinical_use",
                "clinic_id": 3,
            },
        )
        check("zero consumption quantity rejected", r.status_code == 422, r.text)

        orders_before = client.get("/inventory/orders", headers=auth)
        check("GET /inventory/orders authenticated", orders_before.status_code == 200, orders_before.text)
        order_count_before = len(orders_before.json()) if orders_before.status_code == 200 else 0
        if orders_before.status_code == 200:
            order_rows = orders_before.json()
            check(
                "order list includes supply_id, user_uuid, and supply data",
                all(
                    "supply_id" in row
                    and "user_uuid" in row
                    and "supply_name" in row
                    and "clinic_id" in row
                    for row in order_rows
                ),
                str(order_rows[:1]),
            )
            check(
                "order list contains deliveries and consumptions",
                any(row.get("order_type") == "delivery" and row.get("vendor_name") for row in order_rows)
                and any(row.get("order_type") == "consumption" and row.get("consumption_type") for row in order_rows),
            )
            check("order list does not use product_id", all("product_id" not in row for row in order_rows))

        expected_message = INSUFFICIENT_STOCK_TEMPLATE.format(
            name=created.get("name"),
            available=8,
            quantity=9,
        )
        r = client.post(
            "/inventory/orders/outbound",
            headers=auth,
            json={
                "supply_id": created.get("id"),
                "quantity": 9,
                "consumption_type": "expiry_waste",
                "clinic_id": 3,
            },
        )
        check("excessive consumption -> HTTP 400", r.status_code == 400, r.text)
        check(
            "insufficient-stock message is exact",
            r.status_code == 400 and r.json().get("detail") == expected_message,
            f"got={r.text} expected={expected_message}",
        )

        r = client.get(f"/inventory/products/{created.get('id')}", headers=auth)
        check("stock unchanged after rejected consumption", r.status_code == 200 and r.json().get("current_stock") == 8, r.text)
        orders_after = client.get("/inventory/orders", headers=auth)
        order_count_after = len(orders_after.json()) if orders_after.status_code == 200 else -1
        check("rejected consumption did not persist", order_count_after == order_count_before, str(order_count_after))

        with Session(get_engine()) as session:
            supplies = session.exec(select(MedicalSupply)).all()
            deliveries = session.exec(select(SupplyDelivery)).all()
            consumptions = session.exec(select(SupplyConsumption)).all()
            check("ORM MedicalSupply rows exist", len(supplies) >= len(SEED_SUPPLIES))
            check("at least four SupplyDelivery rows", len(deliveries) >= 4, str(len(deliveries)))
            check("at least three SupplyConsumption rows", len(consumptions) >= 3, str(len(consumptions)))
            check(
                "no stock column on MedicalSupply",
                not hasattr(MedicalSupply, "stock") and not hasattr(MedicalSupply, "current_stock"),
            )
            glove_supply = next(row for row in supplies if row.sku == "HCR-PPE-001")
            glove_deliveries = [row for row in deliveries if row.supply_id == glove_supply.id]
            glove_quantities = sorted(row.quantity for row in glove_deliveries)
            check(
                "HCR-PPE-001 has at least two deliveries with different quantities",
                len(glove_deliveries) >= 2 and len(set(glove_quantities)) >= 2,
                str(glove_quantities),
            )
            consumption_types = {row.consumption_type for row in consumptions}
            check(
                "consumptions include clinical_use and expiry_waste",
                {"clinical_use", "expiry_waste"} <= consumption_types,
                str(consumption_types),
            )
            check("delivery FK uses supply_id", all(row.supply_id is not None for row in deliveries))
            check("all clinic_id values are 1-12", all(1 <= row.clinic_id <= 12 for row in [*deliveries, *consumptions]))

            before_repeat = (len(supplies), len(deliveries), len(consumptions))
            seed_inventory_if_empty(session)
            after_supplies = session.exec(select(MedicalSupply)).all()
            after_deliveries = session.exec(select(SupplyDelivery)).all()
            after_consumptions = session.exec(select(SupplyConsumption)).all()
            check(
                "repeated seed does not duplicate movements",
                (len(after_supplies), len(after_deliveries), len(after_consumptions)) == before_repeat,
                str((len(after_supplies), len(after_deliveries), len(after_consumptions))),
            )

        from app.db import database as database_module

        check("get_db is a request-scoped generator", inspect.isgeneratorfunction(get_db))
        check(
            "no global SQLModel session",
            database_module.__dict__.get("session") is None
            and database_module.__dict__.get("SessionLocal") is None,
        )
        check("TinyDB identity file exists", Path(settings.tinydb_path).exists())
        check("SQL inventory file exists", Path(_sqlite_path).exists())
        check("obsolete ClinicalSupply name removed", "ClinicalSupply" not in MedicalSupply.__name__)
        check("seed constants include required HCR SKUs", {row["sku"] for row in SEED_SUPPLIES} == set(REQUIRED_SKUS))
        check("seed deliveries >= 4", len(SEED_DELIVERIES) >= 4)
        check("seed consumptions >= 3", len(SEED_CONSUMPTIONS) >= 3)

    print()
    if failures:
        print(f"{len(failures)} failure(s): {failures}")
        return 1
    print("All HealthCore inventory acceptance checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
