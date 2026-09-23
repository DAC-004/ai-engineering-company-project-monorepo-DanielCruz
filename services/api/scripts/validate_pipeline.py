"""Validate the HealthCore Monthly Clinic Supply Performance pipeline and reporting API."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

_tmpdir = tempfile.mkdtemp(prefix="pipeline-")
_sqlite_path = (Path(_tmpdir) / "pipeline.db").resolve().as_posix()
os.environ["SECRET_KEY"] = "validation-secret-key-32chars!!"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["TINYDB_PATH"] = str(Path(_tmpdir) / "auth.json")
os.environ["DATABASE_URL"] = f"sqlite:///{_sqlite_path}"
os.environ["TELEMETRY_ENDPOINT"] = "http://localhost:8000/telemetry/events"
os.environ["PREFECT_HOME"] = str((Path(_tmpdir) / "pf").resolve())
os.environ.pop("PREFECT_API_URL", None)

from unittest.mock import patch

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import get_engine, init_databases, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from data.pipelines.pipeline import (  # noqa: E402
    extract_supply_performance_events,
    load_monthly_clinic_supply_performance,
    run_monthly_clinic_supply_performance,
    transform_cache_key,
    transform_monthly_clinic_aggregates,
    write_eval_snapshot,
)
from prefect import flow as prefect_flow  # noqa: E402
from data.pipelines.reporting_store import (  # noqa: E402
    extract_supply_performance_events as store_extract_supply_performance_events,
    get_monthly_clinic_supply_performance,
    qualify,
)
from data.pipelines.transforms import (  # noqa: E402
    transform_monthly_clinic_aggregates as compute_aggregates,
)
from services.telemetry import analysis as telemetry_analysis  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()
reset_engine_for_tests()

MONTH = date(2026, 7, 1)
ANALYSIS_PATH = REPO_ROOT / "services" / "telemetry" / "analysis.py"
TELEMETRY_ROUTER_PATH = API_DIR / "app" / "routers" / "telemetry.py"


def _auth_header(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": password})
    token = response.json().get("access_token")
    if response.status_code != 200 or not token:
        raise RuntimeError(f"login failed: {response.status_code} {response.text}")
    return {"Authorization": f"Bearer {token}"}


def _insert_event(
    connection,
    *,
    timestamp: datetime,
    event_type: str,
    tags: dict,
    event_id: str | None = None,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO telemetry_events (
                event_id, timestamp, session_id, user_id, event_type,
                schema_version, request_id, tags
            ) VALUES (
                :event_id, :timestamp, :session_id, :user_id, :event_type,
                :schema_version, :request_id, :tags
            )
            """
        ),
        {
            "event_id": event_id or str(uuid4()),
            "timestamp": timestamp,
            "session_id": str(uuid4()),
            "user_id": "staff-user-not-for-reporting",
            "event_type": event_type,
            "schema_version": "1.0.0",
            "request_id": str(uuid4()),
            "tags": json.dumps(tags),
        },
    )


def _seed_july_events(connection) -> None:
    july = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    _insert_event(
        connection,
        timestamp=july,
        event_type="inbound_order_created",
        tags={
            "clinic_id": 3,
            "country": "US",
            "product_id": 1,
            "product_category": "ppe",
            "quantity": 10,
            "vendor_name": "MedLine Industries",
            "inbound_order_id": 41,
            "total_cost": 100.50,
        },
        event_id="11111111-1111-1111-1111-111111111111",
    )
    _insert_event(
        connection,
        timestamp=july + timedelta(hours=1),
        event_type="inbound_order_created",
        tags={
            "clinic_id": 3,
            "country": "US",
            "product_id": 1,
            "product_category": "ppe",
            "quantity": 2,
            "vendor_name": "MedLine Industries",
            "inbound_order_id": 42,
            "total_cost": 20,
        },
    )
    _insert_event(
        connection,
        timestamp=july,
        event_type="inbound_order_created",
        tags={
            "clinic_id": 3,
            "country": "US",
            "product_id": 1,
            "product_category": "ppe",
            "quantity": 2,
            "vendor_name": "MedLine Industries",
            "inbound_order_id": 41,
            "total_cost": 999,
        },
        event_id="22222222-2222-2222-2222-222222222222",
    )
    _insert_event(
        connection,
        timestamp=july,
        event_type="inbound_order_created",
        tags={
            "clinic_id": 3,
            "country": "US",
            "product_id": 1,
            "product_category": "ppe",
            "quantity": 1,
            "vendor_name": "MedLine Industries",
            "inbound_order_id": 43,
        },
    )
    _insert_event(
        connection,
        timestamp=july,
        event_type="outbound_order_created",
        tags={
            "clinic_id": 3,
            "country": "US",
            "product_id": 1,
            "product_category": "ppe",
            "quantity": 2,
            "department": "primary_care",
            "outbound_order_id": 17,
        },
    )
    _insert_event(
        connection,
        timestamp=july,
        event_type="outbound_order_created",
        tags={
            "clinic_id": 3,
            "country": "US",
            "product_id": 1,
            "product_category": "ppe",
            "quantity": 1,
            "department": "specialty_care",
            "outbound_order_id": 18,
        },
    )
    _insert_event(
        connection,
        timestamp=july,
        event_type="stock_threshold_triggered",
        tags={
            "clinic_id": 3,
            "country": "US",
            "product_id": 1,
            "product_category": "ppe",
            "quantity": 4,
            "minimum_stock": 10,
            "triggering_outbound_order_id": 17,
        },
    )
    _insert_event(
        connection,
        timestamp=july,
        event_type="supply_expiry_flagged",
        tags={
            "clinic_id": 3,
            "country": "US",
            "product_id": 1,
            "product_category": "ppe",
            "quantity": 3,
            "expiry_date": "2026-07-20",
            "days_until_expiry": 5,
            "expiry_window_days": 30,
        },
    )
    _insert_event(
        connection,
        timestamp=july,
        event_type="inbound_order_created",
        tags={
            "clinic_id": 11,
            "country": "UK",
            "product_id": 2,
            "product_category": "medication",
            "quantity": 4,
            "vendor_name": "UK Supplies Ltd",
            "inbound_order_id": 80,
            "total_cost": 50,
        },
    )
    _insert_event(
        connection,
        timestamp=july,
        event_type="outbound_order_created",
        tags={
            "clinic_id": 11,
            "country": "UK",
            "product_id": 2,
            "product_category": "medication",
            "quantity": 1,
            "department": "chronic_care",
            "outbound_order_id": 90,
        },
    )
    _insert_event(
        connection,
        timestamp=july,
        event_type="supply_expiry_flagged",
        tags={
            "clinic_id": 11,
            "country": "UK",
            "product_id": 2,
            "product_category": "medication",
            "quantity": 1,
            "expiry_date": "2026-07-25",
            "days_until_expiry": 10,
            "expiry_window_days": 30,
        },
    )
    _insert_event(
        connection,
        timestamp=july,
        event_type="supply_expiry_flagged",
        tags={
            "clinic_id": 11,
            "country": "UK",
            "product_id": 3,
            "product_category": "ppe",
            "quantity": 1,
            "expiry_date": "2026-07-28",
            "days_until_expiry": 13,
            "expiry_window_days": 30,
        },
    )
    _insert_event(
        connection,
        timestamp=datetime(2026, 6, 15, tzinfo=UTC),
        event_type="inbound_order_created",
        tags={
            "clinic_id": 3,
            "country": "US",
            "product_id": 1,
            "product_category": "ppe",
            "quantity": 1,
            "vendor_name": "MedLine Industries",
            "inbound_order_id": 9,
            "total_cost": 5000,
        },
    )
    _insert_event(
        connection,
        timestamp=july,
        event_type="page_viewed",
        tags={"route": "/backoffice/inventory/products"},
    )


def main() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"PASS  {name}")
        else:
            failures.append(name)
            print(f"FAIL  {name} {detail}")

    init_databases()
    engine = get_engine()
    with engine.begin() as connection:
        _seed_july_events(connection)

    transform_source = (REPO_ROOT / "data" / "pipelines" / "transforms.py").read_text(
        encoding="utf-8"
    )
    pipeline_source = (REPO_ROOT / "data" / "pipelines" / "pipeline.py").read_text(
        encoding="utf-8"
    )
    analysis_before = ANALYSIS_PATH.read_text(encoding="utf-8")
    telemetry_router_before = TELEMETRY_ROUTER_PATH.read_text(encoding="utf-8")

    check("python data/pipelines/pipeline.py exists", Path(REPO_ROOT / "data" / "pipelines" / "pipeline.py").is_file())
    check("@flow is defined", "@flow" in pipeline_source)
    check("extract task exists", "def extract_supply_performance_events" in pipeline_source)
    check("transform task exists", "def transform_monthly_clinic_aggregates" in pipeline_source)
    check("load task exists", "def load_monthly_clinic_supply_performance" in pipeline_source)
    check(
        "production CLI/flow does not bypass Prefect with .fn()",
        ".fn(" not in pipeline_source,
        "pipeline.py still contains .fn(",
    )
    entry_source = pipeline_source.split("def run_monthly_clinic_supply_performance", 1)[-1].split("def get_monthly_clinic_supply_performance", 1)[0]
    check(
        "CLI/API entry submits the Prefect flow",
        "monthly_clinic_supply_performance_flow(" in entry_source,
        entry_source[:400],
    )
    check(
        "extract retries greater than zero with justification comment",
        "retries=3" in pipeline_source and "Three retries" in pipeline_source,
    )
    check(
        "load retries greater than zero with justification comment",
        "retries=1" in pipeline_source and "One retry" in pipeline_source,
    )
    check("extract retries configured", extract_supply_performance_events.retries == 3)
    check("load retries configured", load_monthly_clinic_supply_performance.retries == 1)
    check(
        "transform cache_key_fn and cache_expiration",
        transform_monthly_clinic_aggregates.cache_key_fn is transform_cache_key
        and transform_monthly_clinic_aggregates.cache_expiration == timedelta(hours=1),
    )
    check("optional snapshot uses return_state=True", "return_state=True" in pipeline_source)
    check("flow continues after inspecting optional snapshot state", "_handle_optional_snapshot_state" in pipeline_source)
    check("CLI documents python data/pipelines/pipeline.py", "python data/pipelines/pipeline.py" in pipeline_source)

    july_key = transform_cache_key(None, {"month_start": date(2026, 7, 1), "events": [{"event_id": "a"}]})
    august_key = transform_cache_key(None, {"month_start": date(2026, 8, 1), "events": [{"event_id": "a"}]})
    other_events_key = transform_cache_key(
        None, {"month_start": date(2026, 7, 1), "events": [{"event_id": "b"}]}
    )
    check("cache key differs by month", july_key != august_key)
    check("cache key differs by extracted event set", july_key != other_events_key)

    events = [
        {
            "event_id": "e1",
            "timestamp": datetime(2026, 7, 2, tzinfo=UTC),
            "event_type": "inbound_order_created",
            "tags": {
                "clinic_id": 3,
                "country": "US",
                "inbound_order_id": 1,
                "total_cost": 10.25,
            },
        },
        {
            "event_id": "e1",
            "timestamp": datetime(2026, 7, 2, tzinfo=UTC),
            "event_type": "inbound_order_created",
            "tags": {
                "clinic_id": 3,
                "country": "US",
                "inbound_order_id": 99,
                "total_cost": 999,
            },
        },
        {
            "event_id": "e2",
            "timestamp": datetime(2026, 7, 3, tzinfo=UTC),
            "event_type": "outbound_order_created",
            "tags": {
                "clinic_id": 3,
                "country": "US",
                "outbound_order_id": 7,
                "department": "primary_care",
            },
        },
        {
            "event_id": "e3",
            "timestamp": datetime(2026, 7, 3, tzinfo=UTC),
            "event_type": "stock_threshold_triggered",
            "tags": {"clinic_id": 3, "country": "US"},
        },
        {
            "event_id": "e4",
            "timestamp": datetime(2026, 7, 3, tzinfo=UTC),
            "event_type": "supply_expiry_flagged",
            "tags": {"clinic_id": 3, "country": "US"},
        },
        {
            "event_id": "e5",
            "timestamp": datetime(2026, 7, 3, tzinfo=UTC),
            "event_type": "inbound_order_created",
            "tags": {
                "clinic_id": 11,
                "country": "UK",
                "inbound_order_id": 2,
                "total_cost": 5,
            },
        },
        {
            "event_id": "e6",
            "timestamp": datetime(2026, 7, 3, tzinfo=UTC),
            "event_type": "inbound_order_created",
            "tags": {
                "clinic_id": 3,
                "country": "US",
                "inbound_order_id": 8,
                "total_cost": -1,
            },
        },
    ]
    computed = compute_aggregates(events, MONTH)
    clinic_3 = next(row for row in computed["aggregates"] if row["clinic_id"] == "3")
    clinic_11 = next(row for row in computed["aggregates"] if row["clinic_id"] == "11")
    check("supply cost sums tags.total_cost", clinic_3["total_supply_cost"] == Decimal("10.25"))
    check("consumption is event count not quantity", clinic_3["supply_consumption_count"] == 1)
    check("stockout count", clinic_3["critical_stockout_count"] == 1)
    check("expiry count", clinic_3["expiry_risk_count"] == 1)
    check("US currency is USD", clinic_3["currency"] == "USD")
    check("UK currency is GBP", clinic_11["currency"] == "GBP" and clinic_11["total_supply_cost"] == Decimal("5"))
    check("negative total_cost rejected", computed["records_rejected"] >= 2)
    check("department is not a destination field", "department" not in clinic_3)
    check("transform never writes telemetry_events", "telemetry_events" not in transform_source.split("def transform_monthly_clinic_aggregates")[1][:800] or "never touches" in transform_source)

    snapshot_dir = Path(_tmpdir) / "eval-dir"
    snapshot_dir.mkdir()
    extract_attempts = {"count": 0}

    def flaky_extract(engine, month_start):
        extract_attempts["count"] += 1
        if extract_attempts["count"] == 1:
            raise ConnectionError("transient pooler disconnect")
        return store_extract_supply_performance_events(engine, month_start)

    with patch("data.pipelines.pipeline.read_supply_performance_events", flaky_extract):
        first = run_monthly_clinic_supply_performance(month_start=MONTH, trigger_type="manual")
    check("extract retried after transient failure", extract_attempts["count"] == 2, str(extract_attempts))
    check("first flow completed after retry", first["status"] == "Completed", str(first))
    check(
        "run metadata has five required fields",
        all(
            key in first
            for key in ("started_at", "finished_at", "records_processed", "status", "error_message")
        ),
        str(first.keys()),
    )
    report = get_monthly_clinic_supply_performance(engine, MONTH)
    check("report returned", report is not None)
    assert report is not None
    check("twelve clinic rows after completed run", len(report["clinics"]) == 12, str(len(report["clinics"])))
    by_id = {row["clinic_id"]: row for row in report["clinics"]}
    check("clinic 3 supply cost", by_id["3"]["total_supply_cost"] == 120.5, str(by_id["3"]))
    check("clinic 3 consumption count", by_id["3"]["supply_consumption_count"] == 2)
    check("clinic 3 stockout count", by_id["3"]["critical_stockout_count"] == 1)
    check("clinic 3 expiry count", by_id["3"]["expiry_risk_count"] == 1)
    check("clinic 3 USD", by_id["3"]["currency"] == "USD" and by_id["3"]["country"] == "US")
    check("clinic 11 GBP not mixed into US", by_id["11"]["currency"] == "GBP" and by_id["11"]["total_supply_cost"] == 50)
    check("clinic 11 expiry count", by_id["11"]["expiry_risk_count"] == 2)
    check("idle clinic zero row", by_id["1"]["total_supply_cost"] == 0 and by_id["1"]["currency"] == "USD")
    check("clinic_id is text live id", by_id["3"]["clinic_id"] == "3")
    serialized = json.dumps(report)
    check("report has no PHI", "patient" not in serialized.lower() and "staff-user-not-for-reporting" not in serialized)

    dest = qualify(engine, "monthly_clinic_supply_performance")
    with engine.connect() as connection:
        count_before = connection.execute(text(f"SELECT COUNT(*) FROM {dest} WHERE month_start = :m"), {"m": MONTH.isoformat()}).scalar()
    second = run_monthly_clinic_supply_performance(month_start=MONTH, trigger_type="manual")
    check("second flow completed", second["status"] == "Completed", str(second))
    with engine.connect() as connection:
        count_after = connection.execute(text(f"SELECT COUNT(*) FROM {dest} WHERE month_start = :m"), {"m": MONTH.isoformat()}).scalar()
        costs = list(
            connection.execute(
                text(f"SELECT clinic_id, total_supply_cost FROM {dest} WHERE month_start = :m ORDER BY clinic_id"),
                {"m": MONTH.isoformat()},
            )
        )
    check("repeat load does not duplicate clinic-month rows", count_before == count_after == 12, f"{count_before} {count_after}")
    cost_map = {row[0]: float(row[1]) for row in costs}
    check("repeat load keeps identical KPI values", cost_map.get("3") == 120.5 and cost_map.get("11") == 50.0, str(cost_map))

    failed_optional = run_monthly_clinic_supply_performance(
        month_start=MONTH,
        trigger_type="manual",
        eval_snapshot_path=str(snapshot_dir),
    )
    check(
        "optional snapshot failure does not fail ETL",
        failed_optional["status"] == "Completed",
        str(failed_optional),
    )

    @prefect_flow(name="optional_snapshot_state_probe")
    def optional_snapshot_state_probe() -> dict[str, str | bool]:
        state = write_eval_snapshot(
            {"aggregates": [], "records_extracted": 0, "records_rejected": 0},
            MONTH,
            str(snapshot_dir),
            return_state=True,
        )
        return {"failed": state.is_failed(), "name": state.name}

    snapshot_probe = optional_snapshot_state_probe()
    check(
        "optional snapshot returns a failed Prefect task state",
        snapshot_probe["failed"] is True,
        str(snapshot_probe),
    )

    cache_events = [
        {
            "event_id": "cache-probe-1",
            "timestamp": datetime(2026, 7, 2, tzinfo=UTC),
            "event_type": "outbound_order_created",
            "tags": {
                "clinic_id": 3,
                "country": "US",
                "outbound_order_id": 701,
            },
        }
    ]

    @prefect_flow(name="transform_cache_probe")
    def transform_cache_probe() -> dict[str, str]:
        first_state = transform_monthly_clinic_aggregates(cache_events, MONTH, return_state=True)
        second_state = transform_monthly_clinic_aggregates(cache_events, MONTH, return_state=True)
        return {"first": first_state.name, "second": second_state.name}

    cache_probe = transform_cache_probe()
    check("transform cache miss then hit", cache_probe["first"] == "Completed" and cache_probe["second"] == "Cached", str(cache_probe))

    cli_env = os.environ.copy()
    cli_env["DATABASE_URL"] = f"sqlite:///{_sqlite_path}"
    cli_env["PREFECT_HOME"] = str((Path(_tmpdir) / "pf-cli").resolve())
    cli_env.pop("PREFECT_API_URL", None)
    cli_result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "data" / "pipelines" / "pipeline.py")],
        cwd=str(REPO_ROOT),
        env=cli_env,
        capture_output=True,
        text=True,
        check=False,
    )
    cli_output = f"{cli_result.stdout}\n{cli_result.stderr}"
    check(
        "python data/pipelines/pipeline.py exits 0",
        cli_result.returncode == 0,
        cli_output[-2000:],
    )
    check(
        "CLI executed the Prefect flow",
        "monthly_clinic_supply_performance_flow" in cli_output and "Beginning flow run" in cli_output,
        cli_output[-2000:],
    )
    check(
        "CLI ran extract as a Prefect task",
        "extract_supply_performance_events" in cli_output and "Task run" in cli_output,
        cli_output[-2000:],
    )
    check(
        "CLI ran transform as a Prefect task",
        "transform_monthly_clinic_aggregates" in cli_output,
        cli_output[-2000:],
    )
    check(
        "CLI ran load as a Prefect task",
        "load_monthly_clinic_supply_performance" in cli_output,
        cli_output[-2000:],
    )

    with TestClient(app) as client:
        r = client.get("/reporting/monthly-clinic-supply-performance")
        check("KPI endpoint requires auth", r.status_code == 401)
        r = client.get("/reporting/pipeline-runs/latest")
        check("latest-run endpoint requires auth", r.status_code == 401)
        r = client.post("/reporting/pipeline-runs", json={"month_start": "2026-07-01"})
        check("trigger endpoint requires auth", r.status_code == 401)

        register = client.post(
            "/users",
            json={"email": "ceo@healthcore.com", "password": "SecurePass1!", "name": "CEO"},
        )
        check("reporting user registered", register.status_code in (200, 201), register.text)
        headers = _auth_header(client, "ceo@healthcore.com", "SecurePass1!")

        r = client.get("/reporting/monthly-clinic-supply-performance?month_start=2026-07-15", headers=headers)
        check("invalid month_start is 422", r.status_code == 422)

        r = client.get("/reporting/monthly-clinic-supply-performance?month_start=2026-07-01", headers=headers)
        check("KPI endpoint 200", r.status_code == 200, r.text)
        body = r.json()
        check("KPI contract month_start", body.get("month_start") == "2026-07-01")
        check("KPI contract clinics list", isinstance(body.get("clinics"), list) and len(body["clinics"]) == 12)
        clinic = next(row for row in body["clinics"] if row["clinic_id"] == "3")
        check(
            "KPI contract fields",
            set(clinic) == {
                "clinic_id",
                "country",
                "total_supply_cost",
                "supply_consumption_count",
                "critical_stockout_count",
                "expiry_risk_count",
                "currency",
            },
            str(clinic.keys()),
        )
        check("no department in API payload", "department" not in clinic)

        r = client.get("/reporting/monthly-clinic-supply-performance", headers=headers)
        check("default month uses latest completed", r.status_code == 200, r.text)

        r = client.get("/reporting/pipeline-runs/latest", headers=headers)
        check("latest run 200", r.status_code == 200, r.text)
        latest = r.json()
        check(
            "latest run exposes status start end records",
            latest.get("status") in {"Completed", "Failed", "Running"}
            and "started_at" in latest
            and "finished_at" in latest
            and "records_processed" in latest,
            str(latest),
        )

        r = client.post("/reporting/pipeline-runs", json={"month_start": "2026-07-01"}, headers=headers)
        check("manual trigger 202", r.status_code == 202, r.text)
        triggered = r.json()
        check("manual trigger returns run_id", bool(triggered.get("run_id")))
        check("manual trigger does not duplicate rows", triggered.get("status") == "Completed", str(triggered))

        r = client.get("/telemetry/report?start_date=2026-07-01T00:00:00Z&end_date=2026-08-01T00:00:00Z")
        check("technical report still served", r.status_code == 200, r.text)
        technical = r.json()
        check(
            "technical report still has operational metrics",
            "metrics" in technical and "events_per_day" in technical.get("metrics", {}),
            str(technical.keys()),
        )

    check(
        "analysis.py unchanged during this validator",
        ANALYSIS_PATH.read_text(encoding="utf-8") == analysis_before,
    )
    check(
        "telemetry router unchanged during this validator",
        TELEMETRY_ROUTER_PATH.read_text(encoding="utf-8") == telemetry_router_before,
    )
    check("analysis module still importable", hasattr(telemetry_analysis, "build_telemetry_report"))
    check("write_eval_snapshot task exists", write_eval_snapshot is not None)

    if failures:
        print(f"\n{len(failures)} pipeline check(s) failed.")
        return 1
    print("\nAll HealthCore business performance pipeline checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
