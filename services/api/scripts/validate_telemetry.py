"""Capture-phase telemetry stub and envelope validation."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

_tmpdir = tempfile.mkdtemp(prefix="telemetry-")
_sqlite_path = (Path(_tmpdir) / "inventory.db").resolve().as_posix()
os.environ["SECRET_KEY"] = "validation-secret-key-32chars!!"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["TINYDB_PATH"] = str(Path(_tmpdir) / "auth.json")
os.environ["DATABASE_URL"] = f"sqlite:///{_sqlite_path}"
os.environ["TELEMETRY_ENDPOINT"] = "http://localhost:8000/telemetry/events"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["INCIDENT_DATA_DIR"] = str(Path(_tmpdir) / "incident-data")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.telemetry import TelemetryEvent  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()
reset_engine_for_tests()

VALID_EVENT = {
    "eventId": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "timestamp": "2026-08-27T14:05:12Z",
    "sessionId": "3d6f0a1b-9c2e-4a77-8f10-21b4c8d9e011",
    "userId": "4b8f1c2a-6d3e-4f90-a1b2-c3d4e5f60718",
    "event_type": "inbound_order_created",
    "schemaVersion": "1.0.0",
    "requestId": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "properties": {
        "clinic_id": 3,
        "country": "US",
        "product_id": 1,
        "product_category": "ppe",
        "quantity": 80,
        "vendor_name": "MedLine Industries",
        "inbound_order_id": 41,
    },
}


def main() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"PASS  {name}")
        else:
            failures.append(name)
            print(f"FAIL  {name} {detail}")

    settings = get_settings()
    check(
        "TELEMETRY_ENDPOINT is read from environment",
        settings.telemetry_endpoint == "http://localhost:8000/telemetry/events",
        settings.telemetry_endpoint,
    )
    check(
        "TelemetryEvent envelope fields",
        set(TelemetryEvent.model_fields)
        == {
            "eventId",
            "timestamp",
            "sessionId",
            "userId",
            "event_type",
            "schemaVersion",
            "requestId",
            "properties",
        },
        str(set(TelemetryEvent.model_fields)),
    )

    frontend_service = (
        REPO_ROOT / "uis" / "talent-pipeline-tracker" / "src" / "services" / "telemetry.ts"
    )
    frontend_source = frontend_service.read_text(encoding="utf-8")
    check("frontend service exists", frontend_service.exists())
    check(
        "frontend endpoint comes from NEXT_PUBLIC_TELEMETRY_ENDPOINT",
        "process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT" in frontend_source,
    )
    check(
        "frontend does not hardcode the telemetry URL",
        "http://localhost:8000/telemetry/events" not in frontend_source
        and "http://127.0.0.1:8000/telemetry/events" not in frontend_source,
    )
    check("frontend queue batch size is 20", "TELEMETRY_MAX_BATCH_SIZE = 20" in frontend_source)
    check(
        "frontend flush interval is 10 seconds",
        "TELEMETRY_FLUSH_INTERVAL_MS = 10_000" in frontend_source,
    )
    # Source-string checks are static evidence only; they do not prove runtime delivery.
    check("frontend uses sendBeacon", "navigator.sendBeacon" in frontend_source)
    check("frontend retries three times", "TELEMETRY_MAX_RETRIES = 3" in frontend_source)
    check(
        "frontend flushes on pagehide as well as visibilitychange",
        'addEventListener("pagehide"' in frontend_source
        and 'addEventListener("visibilitychange"' in frontend_source,
    )

    bootstrap_source = (
        REPO_ROOT
        / "uis"
        / "talent-pipeline-tracker"
        / "components"
        / "telemetry"
        / "TelemetryBootstrap.tsx"
    ).read_text(encoding="utf-8")
    check(
        "full-load page_load_completed remains in TelemetryBootstrap",
        'navigation_type: "full_load"' in bootstrap_source
        and 'track("page_load_completed"' in bootstrap_source,
    )
    check(
        "client navigation does not emit page_load_completed",
        "client_navigation" not in bootstrap_source,
    )
    check(
        "pathname changes still emit page_viewed",
        "trackPageViewed" in bootstrap_source and 'track("page_viewed"' in bootstrap_source,
    )

    auth_guard_source = (
        REPO_ROOT
        / "uis"
        / "talent-pipeline-tracker"
        / "components"
        / "auth"
        / "AuthGuard.tsx"
    ).read_text(encoding="utf-8")
    check(
        "AuthGuard does not emit session_expired on missing token",
        "session_expired" not in auth_guard_source and "track(" not in auth_guard_source,
    )
    api_fetch_source = (
        REPO_ROOT / "uis" / "talent-pipeline-tracker" / "lib" / "auth" / "api.ts"
    ).read_text(encoding="utf-8")
    check(
        "apiFetch still emits session_expired for missing_token",
        'expiry_source: "missing_token"' in api_fetch_source,
    )

    inventory_events_source = (
        REPO_ROOT
        / "uis"
        / "talent-pipeline-tracker"
        / "lib"
        / "telemetry"
        / "inventoryEvents.ts"
    ).read_text(encoding="utf-8")
    check(
        "expiry throttle persists in sessionStorage",
        "sessionStorage" in inventory_events_source
        and "healthcore.telemetry.expiryFlaggedUtcDays" in inventory_events_source,
    )
    check(
        "expiry throttle key is product id plus UTC date",
        "expiryThrottleKey" in inventory_events_source
        and "utcDateKey" in inventory_events_source
        and "${productId}:${utcDateKey()}" in inventory_events_source,
    )
    check(
        "expiry throttle does not use cookies or localStorage",
        "document.cookie" not in inventory_events_source
        and "localStorage" not in inventory_events_source,
    )

    other_frontend = [
        path
        for path in (
            list((REPO_ROOT / "uis" / "talent-pipeline-tracker").rglob("*.ts"))
            + list((REPO_ROOT / "uis" / "talent-pipeline-tracker").rglob("*.tsx"))
        )
        if "node_modules" not in path.parts and ".next" not in path.parts
    ]
    stray_telemetry_fetch = []
    for path in other_frontend:
        if path.resolve() == frontend_service.resolve():
            continue
        text = path.read_text(encoding="utf-8")
        if "telemetry/events" in text or "NEXT_PUBLIC_TELEMETRY_ENDPOINT" in text:
            stray_telemetry_fetch.append(str(path.relative_to(REPO_ROOT)))
    check(
        "no telemetry network calls outside TelemetryService",
        stray_telemetry_fetch == [],
        str(stray_telemetry_fetch),
    )

    with TestClient(app) as client:
        batch = {"events": [VALID_EVENT, {**VALID_EVENT, "event_type": "page_viewed", "properties": {"route": "/"}}]}
        response = client.post("/telemetry/events", json=batch)
        check("POST /telemetry/events HTTP 200", response.status_code == 200, response.text)
        check(
            "response is { received: N }",
            response.status_code == 200 and response.json() == {"received": 2},
            response.text,
        )

        empty = client.post("/telemetry/events", json={"events": []})
        check("empty batch received 0", empty.status_code == 200 and empty.json() == {"received": 0}, empty.text)

        beacon = client.post(
            "/telemetry/events",
            content=b'{"events":[]}',
            headers={"content-type": "text/plain"},
        )
        check("sendBeacon text/plain JSON is accepted", beacon.status_code == 200, beacon.text)

        missing = client.post(
            "/telemetry/events",
            json={"events": [{k: v for k, v in VALID_EVENT.items() if k != "eventId"}]},
        )
        check("invalid envelope rejected", missing.status_code == 422, missing.text)

        extra_root = client.post(
            "/telemetry/events",
            json={"events": [{**VALID_EVENT, "unexpected_root_key": "not-allowed"}]},
        )
        check("extra envelope keys rejected", extra_root.status_code == 422, extra_root.text)

        null_user = client.post(
            "/telemetry/events",
            json={"events": [{**VALID_EVENT, "userId": None, "event_type": "user_login_failed"}]},
        )
        check("userId may be null", null_user.status_code == 200 and null_user.json() == {"received": 1}, null_user.text)

        register = client.post(
            "/users",
            json={"email": "telemetry.clinician@healthcore.com", "password": "SecurePass1!"},
        )
        check("register clinician for inventory checks", register.status_code == 201, register.text)
        login = client.post(
            "/auth/login",
            data={"username": "telemetry.clinician@healthcore.com", "password": "SecurePass1!"},
        )
        token = login.json().get("access_token") if login.status_code == 200 else None
        auth = {"Authorization": f"Bearer {token}"} if token else {}

        products = client.get("/inventory/products", headers=auth)
        check("list products after capture columns", products.status_code == 200, products.text)
        rows = products.json() if products.status_code == 200 else []
        saline = next((row for row in rows if row.get("sku") == "HCR-MED-001"), None)
        check("seed product includes minimum_stock", all("minimum_stock" in row for row in rows), str(rows[:1]))
        check(
            "HCR-MED-001 has expiry_date for supply_expiry_flagged",
            bool(saline and saline.get("expiry_date")),
            str(saline),
        )

        if rows:
            product_id = rows[0]["id"]
            stock_write = client.post(
                "/inventory/products",
                headers=auth,
                json={
                    "name": "Forbidden stock write",
                    "sku": "HCR-TEL-STOCK",
                    "category": "ppe",
                    "unit": "box",
                    "country": "US",
                    "current_stock": 99,
                },
            )
            check(
                "direct stock field on product create is rejected",
                stock_write.status_code == 400,
                stock_write.text,
            )
            patch = client.patch(
                f"/inventory/products/{product_id}",
                headers=auth,
                json={"clinic_id": 1, "current_stock": 250},
            )
            check("PATCH stock is rejected", patch.status_code == 405, patch.text)

            missing_department = client.post(
                "/inventory/orders/outbound",
                headers=auth,
                json={
                    "supply_id": product_id,
                    "quantity": 1,
                    "consumption_type": "clinical_use",
                    "clinic_id": 1,
                },
            )
            check(
                "outbound without department is rejected",
                missing_department.status_code == 422,
                missing_department.text,
            )

            clinic_stock = client.get(
                f"/inventory/products/{product_id}?clinic_id=1",
                headers=auth,
            )
            check(
                "clinic_current_stock is returned when clinic_id is queried",
                clinic_stock.status_code == 200 and "clinic_current_stock" in clinic_stock.json(),
                clinic_stock.text,
            )

    print()
    if failures:
        print(f"{len(failures)} failure(s): {failures}")
        return 1
    print("All HealthCore telemetry capture checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
