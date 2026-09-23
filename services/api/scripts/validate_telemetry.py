"""Telemetry storage endpoint and envelope validation."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event as sqlalchemy_event  # noqa: E402
from sqlalchemy import inspect  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import get_engine, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from app.models import TelemetryEventRecord  # noqa: E402
from app.schemas.telemetry import TelemetryEvent  # noqa: E402
from app.services.telemetry_storage import TELEMETRY_TAG_ALLOWLIST  # noqa: E402

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

CAPTURE_BASELINE = "bb633a6ace683f30bdbf3028fd48512d33e82026"


def make_event(**overrides: Any) -> dict[str, Any]:
    payload = copy.deepcopy(VALID_EVENT)
    payload["eventId"] = str(uuid.uuid4())
    payload["requestId"] = str(uuid.uuid4())
    payload.update(overrides)
    return payload


def extract_class_source(source: str, class_name: str) -> str:
    marker = f"class {class_name}"
    start = source.index(marker)
    rest = source[start:]
    next_class = rest.find("\nclass ", 1)
    chunk = rest[:next_class] if next_class != -1 else rest
    return chunk.strip()


def allowlists_from_event_schemas() -> dict[str, set[str]]:
    schema_path = REPO_ROOT / "docs" / "telemetry" / "event-schemas.json"
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    definitions = data["definitions"]
    mapping: dict[str, set[str]] = {}
    for item in data["oneOf"]:
        event_type = item["allOf"][1]["properties"]["event_type"]["const"]
        ref_name = item["allOf"][1]["properties"]["properties"]["$ref"].rsplit("/", 1)[-1]
        mapping[event_type] = set(definitions[ref_name]["properties"].keys())
    return mapping


def normalize_sql(statement: str) -> str:
    return " ".join(statement.lower().split())


def is_telemetry_insert(statement: str) -> bool:
    compact = normalize_sql(statement)
    return "insert into" in compact and "telemetry_events" in compact


def is_telemetry_update(statement: str) -> bool:
    compact = normalize_sql(statement)
    return compact.startswith("update") and "telemetry_events" in compact


def is_telemetry_delete(statement: str) -> bool:
    compact = normalize_sql(statement)
    return compact.startswith("delete") and "telemetry_events" in compact


class SqlCapture:
    """Record SQL statements executed while a TestClient request runs."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self.statements: list[tuple[str, bool]] = []

    def _before_cursor_execute(
        self,
        _conn,
        _cursor,
        statement: str,
        _parameters,
        _context,
        executemany: bool,
    ) -> None:
        self.statements.append((statement, bool(executemany)))

    def __enter__(self) -> SqlCapture:
        sqlalchemy_event.listen(self.engine, "before_cursor_execute", self._before_cursor_execute)
        return self

    def __exit__(self, *_args: object) -> None:
        sqlalchemy_event.remove(self.engine, "before_cursor_execute", self._before_cursor_execute)

    def telemetry_inserts(self) -> list[str]:
        return [statement for statement, _ in self.statements if is_telemetry_insert(statement)]

    def telemetry_updates(self) -> list[str]:
        return [statement for statement, _ in self.statements if is_telemetry_update(statement)]

    def telemetry_deletes(self) -> list[str]:
        return [statement for statement, _ in self.statements if is_telemetry_delete(statement)]


def load_stored_event(event_id: str) -> TelemetryEventRecord | None:
    with Session(get_engine()) as session:
        return session.exec(
            select(TelemetryEventRecord).where(TelemetryEventRecord.event_id == event_id)
        ).first()


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def counts_match(body: dict[str, Any], received: int, stored: int, rejected: int) -> bool:
    return (
        body.get("received") == received
        and body.get("stored") == stored
        and body.get("rejected") == rejected
        and received == stored + rejected
    )


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

    schema_path = API_DIR / "app" / "schemas" / "telemetry.py"
    current_schema = schema_path.read_text(encoding="utf-8")
    baseline_schema = subprocess.check_output(
        ["git", "show", f"{CAPTURE_BASELINE}:services/api/app/schemas/telemetry.py"],
        cwd=REPO_ROOT,
        text=True,
    )
    check(
        "TelemetryEvent class source is unchanged from capture baseline",
        extract_class_source(current_schema, "TelemetryEvent")
        == extract_class_source(baseline_schema, "TelemetryEvent"),
    )

    router_source = (API_DIR / "app" / "routers" / "telemetry.py").read_text(encoding="utf-8")
    check(
        "handler does not type events as list[TelemetryEvent]",
        "list[TelemetryEvent]" not in router_source
        and "TelemetryBatch" not in router_source,
        "typed batch body would HTTP 422 mixed batches",
    )
    storage_source = (API_DIR / "app" / "services" / "telemetry_storage.py").read_text(
        encoding="utf-8"
    )
    check(
        "storage uses ON CONFLICT DO NOTHING without UPDATE",
        "on_conflict_do_nothing" in storage_source
        and "on_conflict_do_update" not in storage_source
        and "session.merge" not in storage_source,
    )
    check(
        "storage has no telemetry update or delete methods",
        "UPDATE telemetry_events" not in storage_source
        and "DELETE FROM telemetry_events" not in storage_source
        and "session.delete" not in storage_source,
    )

    schema_allowlists = allowlists_from_event_schemas()
    check(
        "Python allowlist covers every event-schemas.json type",
        set(TELEMETRY_TAG_ALLOWLIST) == set(schema_allowlists),
        f"python={sorted(TELEMETRY_TAG_ALLOWLIST)} schema={sorted(schema_allowlists)}",
    )
    allowlist_drift = [
        event_type
        for event_type, keys in schema_allowlists.items()
        if set(TELEMETRY_TAG_ALLOWLIST[event_type]) != keys
    ]
    check(
        "Python allowlist keys match event-schemas.json",
        allowlist_drift == [],
        str(allowlist_drift),
    )

    changed = subprocess.check_output(
        ["git", "diff", "--name-only", CAPTURE_BASELINE],
        cwd=REPO_ROOT,
        text=True,
    ).splitlines()
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        text=True,
    ).splitlines()
    all_changed = changed + untracked
    frontend_changed = [path for path in all_changed if path.startswith("uis/")]
    specs_changed = [path for path in all_changed if path.startswith(".project_specs/")]
    check("no frontend file changes versus capture baseline", frontend_changed == [], str(frontend_changed))
    check(".project_specs is not in the implementation diff", specs_changed == [], str(specs_changed))

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
        engine = get_engine()
        inspector = inspect(engine)
        column_names = [column["name"] for column in inspector.get_columns("telemetry_events")]
        check(
            "telemetry_events has exactly eight approved columns",
            column_names
            == [
                "event_id",
                "timestamp",
                "session_id",
                "user_id",
                "event_type",
                "schema_version",
                "request_id",
                "tags",
            ],
            str(column_names),
        )
        check("telemetry_events has no service column", "service" not in column_names)
        sqlite_indexes = inspector.get_indexes("telemetry_events")
        index_names = {index["name"] for index in sqlite_indexes}
        dedicated_index_columns = {
            index["column_names"][0]
            for index in sqlite_indexes
            if index.get("column_names") == ["timestamp"] or index.get("column_names") == ["event_type"]
        }
        check(
            "SQLite has dedicated indexes covering timestamp and event_type",
            dedicated_index_columns == {"timestamp", "event_type"},
            str(sqlite_indexes),
        )
        check(
            "SQLite skips the PostgreSQL tags GIN index",
            "ix_telemetry_events_tags_gin" not in index_names,
            str(index_names),
        )

        valid_one = make_event()
        valid_two = make_event(
            event_type="page_viewed",
            properties={"route": "/"},
        )
        with SqlCapture(engine) as capture:
            response = client.post("/telemetry/events", json={"events": [valid_one, valid_two]})
        check("POST /telemetry/events HTTP 200", response.status_code == 200, response.text)
        check(
            "all-valid batch returns received stored rejected",
            response.status_code == 200 and counts_match(response.json(), 2, 2, 0),
            response.text,
        )
        check(
            "multi-event accepted batch executes exactly one telemetry INSERT",
            len(capture.telemetry_inserts()) == 1,
            str(capture.telemetry_inserts()),
        )
        check("all-valid batch executes no telemetry UPDATE", capture.telemetry_updates() == [])
        check("all-valid batch executes no telemetry DELETE", capture.telemetry_deletes() == [])

        with SqlCapture(engine) as capture:
            empty = client.post("/telemetry/events", json={"events": []})
        check(
            "empty batch returns 0/0/0",
            empty.status_code == 200 and counts_match(empty.json(), 0, 0, 0),
            empty.text,
        )
        check(
            "empty batch executes no telemetry INSERT",
            capture.telemetry_inserts() == [],
            str(capture.telemetry_inserts()),
        )

        beacon = client.post(
            "/telemetry/events",
            content=b'{"events":[]}',
            headers={"content-type": "text/plain"},
        )
        check(
            "sendBeacon text/plain JSON is accepted",
            beacon.status_code == 200 and counts_match(beacon.json(), 0, 0, 0),
            beacon.text,
        )

        missing = client.post(
            "/telemetry/events",
            json={"events": [{k: v for k, v in make_event().items() if k != "eventId"}]},
        )
        check(
            "invalid envelope item is counted rejected with HTTP 200",
            missing.status_code == 200 and counts_match(missing.json(), 1, 0, 1),
            missing.text,
        )

        extra_root = client.post(
            "/telemetry/events",
            json={"events": [{**make_event(), "unexpected_root_key": "not-allowed"}]},
        )
        check(
            "extra envelope keys are counted rejected with HTTP 200",
            extra_root.status_code == 200 and counts_match(extra_root.json(), 1, 0, 1),
            extra_root.text,
        )

        malformed_json = client.post(
            "/telemetry/events",
            content=b"{not-json",
            headers={"content-type": "application/json"},
        )
        check("invalid JSON returns HTTP 422", malformed_json.status_code == 422, malformed_json.text)
        missing_events_field = client.post("/telemetry/events", json={"items": []})
        check(
            "missing events field returns HTTP 422",
            missing_events_field.status_code == 422,
            missing_events_field.text,
        )
        non_list_events = client.post("/telemetry/events", json={"events": {"event": valid_one}})
        check(
            "non-list events value returns HTTP 422",
            non_list_events.status_code == 422,
            non_list_events.text,
        )

        mixed_valid = make_event()
        mixed_invalid = {k: v for k, v in make_event().items() if k != "timestamp"}
        mixed_valid_two = make_event(event_type="user_login_failed", properties={"failure_reason": "invalid_credentials"})
        with SqlCapture(engine) as capture:
            mixed = client.post(
                "/telemetry/events",
                json={"events": [mixed_valid, mixed_invalid, mixed_valid_two]},
            )
        check(
            "mixed batch HTTP 200 with stored 2 rejected 1",
            mixed.status_code == 200 and counts_match(mixed.json(), 3, 2, 1),
            mixed.text,
        )
        check(
            "mixed batch executes at most one telemetry INSERT",
            len(capture.telemetry_inserts()) == 1,
            str(capture.telemetry_inserts()),
        )
        check("mixed valid event is stored", load_stored_event(mixed_valid["eventId"]) is not None)
        check(
            "mixed invalid event is absent",
            load_stored_event(mixed_invalid["eventId"]) is None,
            mixed_invalid["eventId"],
        )

        with SqlCapture(engine) as capture:
            all_invalid = client.post(
                "/telemetry/events",
                json={"events": [{"nope": True}, {"still": "invalid"}]},
            )
        check(
            "all-invalid batch returns stored 0 rejected 2",
            all_invalid.status_code == 200 and counts_match(all_invalid.json(), 2, 0, 2),
            all_invalid.text,
        )
        check(
            "all-invalid batch executes no telemetry INSERT",
            capture.telemetry_inserts() == [],
            str(capture.telemetry_inserts()),
        )

        bad_timestamp = make_event(timestamp="not-a-datetime")
        sibling = make_event()
        with SqlCapture(engine) as capture:
            timestamp_batch = client.post(
                "/telemetry/events",
                json={"events": [bad_timestamp, sibling]},
            )
        check(
            "unparsable timestamp is rejected without cancelling siblings",
            timestamp_batch.status_code == 200 and counts_match(timestamp_batch.json(), 2, 1, 1),
            timestamp_batch.text,
        )
        check("sibling of bad timestamp is stored", load_stored_event(sibling["eventId"]) is not None)
        check(
            "bad timestamp event is not stored",
            load_stored_event(bad_timestamp["eventId"]) is None,
        )

        offset_event = make_event(timestamp="2026-08-27T15:05:12+01:00")
        offset_response = client.post("/telemetry/events", json={"events": [offset_event]})
        stored_offset = load_stored_event(offset_event["eventId"])
        check(
            "timezone-aware timestamp is stored as UTC",
            offset_response.status_code == 200
            and stored_offset is not None
            and utc_datetime(stored_offset.timestamp) == datetime(2026, 8, 27, 14, 5, 12, tzinfo=UTC),
            str(getattr(stored_offset, "timestamp", None)),
        )

        duplicate_id = str(uuid.uuid4())
        first_dup = make_event(eventId=duplicate_id)
        second_dup = make_event(
            eventId=duplicate_id,
            event_type="page_viewed",
            properties={"route": "/account/profile"},
        )
        with SqlCapture(engine) as capture:
            duplicate_batch = client.post(
                "/telemetry/events",
                json={"events": [first_dup, second_dup]},
            )
        stored_dup = load_stored_event(duplicate_id)
        check(
            "same-batch duplicate keeps the first occurrence",
            duplicate_batch.status_code == 200
            and counts_match(duplicate_batch.json(), 2, 1, 1)
            and stored_dup is not None
            and stored_dup.event_type == "inbound_order_created",
            duplicate_batch.text,
        )
        check(
            "same-batch duplicate still uses one telemetry INSERT",
            len(capture.telemetry_inserts()) == 1,
            str(capture.telemetry_inserts()),
        )

        existing_id = str(uuid.uuid4())
        first_existing = make_event(eventId=existing_id)
        first_store = client.post("/telemetry/events", json={"events": [first_existing]})
        conflict_sibling = make_event()
        with SqlCapture(engine) as capture:
            conflict = client.post(
                "/telemetry/events",
                json={
                    "events": [
                        make_event(eventId=existing_id, event_type="page_viewed", properties={"route": "/"}),
                        conflict_sibling,
                    ]
                },
            )
        stored_existing = load_stored_event(existing_id)
        check(
            "existing-id conflict does not overwrite and does not cancel siblings",
            first_store.status_code == 200
            and conflict.status_code == 200
            and counts_match(conflict.json(), 2, 1, 1)
            and stored_existing is not None
            and stored_existing.event_type == "inbound_order_created"
            and load_stored_event(conflict_sibling["eventId"]) is not None,
            conflict.text,
        )
        check(
            "existing-id conflict uses one telemetry INSERT for the batch",
            len(capture.telemetry_inserts()) == 1,
            str(capture.telemetry_inserts()),
        )
        check("conflict handling executes no telemetry UPDATE", capture.telemetry_updates() == [])

        extra_props = make_event(
            properties={
                **VALID_EVENT["properties"],
                "patient_id": "must-not-be-stored",
                "unexpected": "drop-me",
            }
        )
        extra_response = client.post("/telemetry/events", json={"events": [extra_props]})
        stored_extra = load_stored_event(extra_props["eventId"])
        check(
            "disallowed property keys are stripped from tags",
            extra_response.status_code == 200
            and stored_extra is not None
            and stored_extra.tags == VALID_EVENT["properties"]
            and "patient_id" not in stored_extra.tags
            and "unexpected" not in stored_extra.tags,
            str(getattr(stored_extra, "tags", None)),
        )

        unknown_type = make_event(
            event_type="medical_supply_created",
            properties={"sku": "HCR-MED-001", "clinic_id": 3, "country": "US"},
        )
        unknown_response = client.post("/telemetry/events", json={"events": [unknown_type]})
        stored_unknown = load_stored_event(unknown_type["eventId"])
        check(
            "unknown event_type stores empty tags",
            unknown_response.status_code == 200
            and stored_unknown is not None
            and stored_unknown.tags == {},
            str(getattr(stored_unknown, "tags", None)),
        )

        null_user = make_event(
            userId=None,
            event_type="user_login_failed",
            properties={"failure_reason": "invalid_credentials"},
        )
        null_user_response = client.post("/telemetry/events", json={"events": [null_user]})
        stored_null_user = load_stored_event(null_user["eventId"])
        check(
            "userId may be null",
            null_user_response.status_code == 200
            and counts_match(null_user_response.json(), 1, 1, 0)
            and stored_null_user is not None
            and stored_null_user.user_id is None,
            null_user_response.text,
        )

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
    print("All HealthCore telemetry storage checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
