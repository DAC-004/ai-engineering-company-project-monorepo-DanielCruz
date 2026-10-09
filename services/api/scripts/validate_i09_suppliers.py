"""Isolated supplier auth checks for narrow I09 validation (stdout evidence only)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402


def _run() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="i09-supplier-"))
    suppliers_path = tmp / "suppliers.json"
    auth_path = tmp / "auth.json"
    os.environ["TINYDB_PATH"] = str(auth_path)
    os.environ["SECRET_KEY"] = "isolated-i09-supplier-secret-key-32"
    os.environ["DATABASE_URL"] = f"sqlite:///{(tmp / 'inventory.db').as_posix()}"
    from app import database as supplier_database
    from app.core.config import get_settings
    from app.db.database import reset_engine_for_tests
    from app.db.tinydb import reset_db_for_tests

    supplier_database.DB_PATH = suppliers_path
    supplier_database.DATA_DIR = suppliers_path.parent
    supplier_database.close_db()

    get_settings.cache_clear()
    reset_db_for_tests()
    reset_engine_for_tests()

    client = TestClient(app)
    payload = {
        "name": "I09 Validation Supplier",
        "country": "USA",
        "categories": ["medical_supplies"],
        "monthly_rate": 1200.5,
        "currency": "USD",
        "status": "active",
    }

    unauth = client.post("/suppliers", json=payload)
    if unauth.status_code != 401:
        print(f"FAIL unauthenticated create expected 401 got {unauth.status_code}")
        return 1

    register = client.post(
        "/users",
        json={"email": "i09.supplier@example.com", "password": "test-password-1"},
    )
    if register.status_code not in {200, 201}:
        print(f"FAIL register {register.status_code}")
        return 1

    login = client.post(
        "/auth/login",
        data={"username": "i09.supplier@example.com", "password": "test-password-1"},
    )
    if login.status_code != 200:
        print(f"FAIL login {login.status_code}")
        return 1
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post("/suppliers", json=payload, headers=headers)
    if created.status_code != 201:
        print(f"FAIL authenticated create {created.status_code} {created.text}")
        return 1
    supplier_id = created.json()["id"]

    rate = client.patch(
        f"/suppliers/{supplier_id}/rate",
        json={"monthly_rate": 1500},
        headers=headers,
    )
    if rate.status_code != 200 or rate.json()["monthly_rate"] != 1500:
        print(f"FAIL rate update {rate.status_code}")
        return 1

    status = client.patch(
        f"/suppliers/{supplier_id}/status",
        json={"status": "suspended"},
        headers=headers,
    )
    if status.status_code != 200 or status.json()["status"] != "suspended":
        print(f"FAIL status update {status.status_code}")
        return 1

    listed = client.get("/suppliers")
    if not any(row["id"] == supplier_id for row in listed.json()):
        print("FAIL list missing created supplier")
        return 1

    supplier_database.close_db()
    client2 = TestClient(app)
    after_restart = client2.get("/suppliers")
    if not any(row["id"] == supplier_id for row in after_restart.json()):
        print("FAIL supplier missing after simulated restart")
        return 1

    print(
        json.dumps(
            {
                "unauthenticated_create": unauth.status_code,
                "authenticated_create": created.status_code,
                "rate_update": rate.status_code,
                "status_update": status.status_code,
                "supplier_id": supplier_id,
                "retained_after_restart": True,
                "suppliers_db": str(suppliers_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
