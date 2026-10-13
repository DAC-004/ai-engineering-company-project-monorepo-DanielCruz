"""Validate the telemetry analysis pipeline and GET /telemetry/report."""

from __future__ import annotations

import ast
import csv
import json
import os
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

_tmpdir = tempfile.mkdtemp(prefix="telemetry-report-")
_sqlite_path = (Path(_tmpdir) / "inventory.db").resolve().as_posix()
os.environ["SECRET_KEY"] = "validation-secret-key-32chars!!"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["TINYDB_PATH"] = str(Path(_tmpdir) / "auth.json")
os.environ["DATABASE_URL"] = f"sqlite:///{_sqlite_path}"
os.environ["TELEMETRY_ENDPOINT"] = "http://localhost:8000/telemetry/events"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import get_engine, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import telemetry as telemetry_router  # noqa: E402
from services.telemetry import analysis as telemetry_analysis  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()
reset_engine_for_tests()

ANALYSIS_PATH = REPO_ROOT / "services" / "telemetry" / "analysis.py"
START = datetime(2026, 9, 1, tzinfo=UTC)
END = datetime(2026, 9, 3, tzinfo=UTC)
WINDOW_END_EXCLUSIVE = datetime(2026, 9, 2, tzinfo=UTC)

METRIC_FUNCTIONS = (
    "events_per_day",
    "error_rate_by_type",
    "latency_by_route",
)
APPROVED_METRIC_KEYS = set(METRIC_FUNCTIONS)


def _insert_event(
    connection,
    *,
    timestamp: datetime,
    event_type: str,
    tags: dict | None = None,
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
            "event_id": str(uuid4()),
            "timestamp": timestamp,
            "session_id": str(uuid4()),
            "user_id": None,
            "event_type": event_type,
            "schema_version": "1.0.0",
            "request_id": str(uuid4()),
            "tags": json.dumps(tags or {}),
        },
    )


def _seed_telemetry_events() -> None:
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS telemetry_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    session_id TEXT,
                    user_id TEXT,
                    event_type TEXT NOT NULL,
                    schema_version TEXT,
                    request_id TEXT,
                    tags TEXT
                )
                """
            )
        )
        connection.execute(text("DELETE FROM telemetry_events"))
        _insert_event(
            connection,
            timestamp=START,
            event_type="page_viewed",
            tags={"route": "/"},
        )
        _insert_event(
            connection,
            timestamp=WINDOW_END_EXCLUSIVE,
            event_type="page_viewed",
            tags={"route": "/login"},
        )
        _insert_event(
            connection,
            timestamp=START - timedelta(seconds=1),
            event_type="page_viewed",
            tags={"route": "/before-window"},
        )
        _insert_event(
            connection,
            timestamp=datetime(2026, 9, 1, 12, tzinfo=UTC),
            event_type="user_login_failed",
            tags={"failure_reason": "invalid_credentials"},
        )
        _insert_event(
            connection,
            timestamp=datetime(2026, 9, 2, 10, tzinfo=UTC),
            event_type="user_login_failed",
            tags={"failure_reason": "invalid_credentials"},
        )
        _insert_event(
            connection,
            timestamp=datetime(2026, 9, 1, 14, tzinfo=UTC),
            event_type="api_request_completed",
            tags={
                "http_method": "GET",
                "route_template": "/inventory/products",
                "status_code": 200,
                "duration_ms": 100,
                "outcome": "success",
            },
        )
        _insert_event(
            connection,
            timestamp=datetime(2026, 9, 1, 15, tzinfo=UTC),
            event_type="api_request_completed",
            tags={
                "http_method": "POST",
                "route_template": "/auth/login",
                "status_code": 401,
                "duration_ms": 200,
                "outcome": "client_error",
            },
        )
        _insert_event(
            connection,
            timestamp=datetime(2026, 9, 1, 16, tzinfo=UTC),
            event_type="api_request_completed",
            tags={
                "http_method": "GET",
                "route_template": "/inventory/products/{id}",
                "status_code": 200,
                "outcome": "success",
            },
        )
        _insert_event(
            connection,
            timestamp=datetime(2026, 9, 1, 17, tzinfo=UTC),
            event_type="frontend_error_uncaught",
            tags={
                "error_name": "TypeError",
                "sanitized_message": "undefined",
                "route": "/",
                "stack_hash": "a" * 64,
            },
        )
        _insert_event(
            connection,
            timestamp=datetime(2026, 9, 1, 18, tzinfo=UTC),
            event_type="outbound_order_created",
            tags={"clinic_id": 1, "country": "US"},
        )


def _replay_supplied_export() -> None:
    """Print aggregate metrics from the local export. This is not a live HTTP sample."""
    export_path = REPO_ROOT / ".project_specs" / "telemetry_events_rows.csv"
    print()
    print("EXPORT REPLAY (isolated engine; not a live HTTP response from Supabase)")
    if not export_path.is_file():
        print("BLOCKED  supplied export is not available locally")
        return

    identifier_fields = ("event_id", "request_id", "session_id", "user_id")
    replay_dir = Path(tempfile.mkdtemp(prefix="telemetry-export-replay-"))
    replay_engine = create_engine(
        f"sqlite:///{(replay_dir / 'replay.db').resolve().as_posix()}"
    )
    inserted = 0
    with replay_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE telemetry_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    session_id TEXT,
                    user_id TEXT,
                    event_type TEXT NOT NULL,
                    schema_version TEXT,
                    request_id TEXT,
                    tags TEXT
                )
                """
            )
        )
        with export_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                parsed = datetime.fromisoformat(row["timestamp"].replace("+00", "+00:00"))
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
                        "event_id": str(uuid4()),
                        "timestamp": parsed,
                        "session_id": None,
                        "user_id": None,
                        "event_type": row["event_type"],
                        "schema_version": row.get("schema_version") or "1.0.0",
                        "request_id": None,
                        "tags": row["tags"],
                    },
                )
                inserted += 1

    report = telemetry_analysis.build_telemetry_report(
        datetime(2026, 9, 4, tzinfo=UTC),
        datetime(2026, 9, 5, tzinfo=UTC),
        engine=replay_engine,
    )
    serialized = json.dumps(report, indent=2)
    leaked = [field for field in identifier_fields if field in serialized]
    if leaked:
        print(f"BLOCKED  replay output contained identifier field names: {leaked}")
        return
    volume_dates = {row["date"] for row in report["metrics"]["events_per_day"]}
    print(f"replayed_row_count {inserted}")
    print(f"volume_utc_dates {sorted(volume_dates)}")
    print(serialized)


def _function_source(tree: ast.Module, name: str) -> str:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(ANALYSIS_PATH.read_text(encoding="utf-8"), node) or ""
    return ""


def main() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"PASS  {name}")
        else:
            failures.append(name)
            print(f"FAIL  {name} {detail}")

    analysis_source = ANALYSIS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(analysis_source)
    defined = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    }

    check("services/telemetry/analysis.py exists", ANALYSIS_PATH.is_file())
    check(
        "at least three independent metric functions",
        len([name for name in METRIC_FUNCTIONS if name in defined]) >= 3,
        str(sorted(defined)),
    )

    loop_nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.For, ast.While, ast.AsyncFor))
    ]
    check("analysis.py has no metric-calculation loops", loop_nodes == [], str(loop_nodes))
    check("analysis.py does not apply its own 7-day default", "timedelta(days=7)" not in analysis_source)
    check(
        "auth_failure_rate is not implemented",
        "auth_failure_rate" not in defined and "user_login_succeeded" not in analysis_source,
        str(sorted(defined)),
    )

    for function_name in METRIC_FUNCTIONS:
        source = _function_source(tree, function_name)
        check(f"{function_name} loads with SQL", "SELECT" in source and "FROM telemetry_events" in source)
        check(
            f"{function_name} applies inclusive/exclusive timestamp bounds in SQL",
            "timestamp >= :start_date" in source and "timestamp < :end_date" in source,
        )
        check(
            f"{function_name} converts timestamps with utc=True",
            "pd.to_datetime" in source and "utc=True" in source,
        )
        check(f"{function_name} groups with groupby", "groupby(" in source)
        check(f"{function_name} aggregates with Pandas", ".agg(" in source or ".count(" in source)
        check(
            f"{function_name} returns to_dict(orient=\"records\")",
            'to_dict(orient="records")' in source or "to_dict(orient='records')" in source,
        )

    check(
        "latency metric filters api_request_completed in SQL",
        "event_type = 'api_request_completed'" in _function_source(tree, "latency_by_route"),
    )

    with TestClient(app) as client:
        _seed_telemetry_events()
        telemetry_router.clear_telemetry_report_cache()
        engine = get_engine()

        first_volume = telemetry_analysis.events_per_day(START, END, engine=engine)
        second_volume = telemetry_analysis.events_per_day(START, END, engine=engine)
        check("events_per_day is deterministic", first_volume == second_volume)
        check("events_per_day is JSON serializable", json.dumps(first_volume) is not None)
        volume_dates = {row["date"] for row in first_volume}
        volume_types = {row["event_type"] for row in first_volume}
        check("events_per_day groups by date and event_type", "date" in first_volume[0] and "event_type" in first_volume[0])
        check("events_per_day includes the inclusive start bound", "2026-09-01" in volume_dates)
        check("events_per_day includes 2026-09-02 when end_date is 2026-09-03", "2026-09-02" in volume_dates)
        check("events_per_day includes captured technical types", "user_login_failed" in volume_types)

        exclusive_volume = telemetry_analysis.events_per_day(START, WINDOW_END_EXCLUSIVE, engine=engine)
        exclusive_dates = {row["date"] for row in exclusive_volume}
        check(
            "SQL end bound excludes an event at end_date",
            exclusive_dates == {"2026-09-01"},
            str(exclusive_dates),
        )

        error_rows = telemetry_analysis.error_rate_by_type(START, END, engine=engine)
        check("error_rate_by_type is JSON serializable", json.dumps(error_rows) is not None)
        error_by_type = {row["event_type"]: row for row in error_rows if row["date"] == "2026-09-01"}
        check("error_rate_by_type groups by date and event_type", "date" in error_rows[0] and "event_type" in error_rows[0])
        check(
            "login failures have error_rate 1.0",
            error_by_type.get("user_login_failed", {}).get("error_rate") == 1.0,
            str(error_by_type.get("user_login_failed")),
        )
        api_error = error_by_type.get("api_request_completed", {})
        check(
            "api_request_completed error rate uses derived is_error",
            api_error.get("error_count") == 1 and api_error.get("event_count") == 3,
            str(api_error),
        )
        check(
            "successful business events are not reported as errors",
            "outbound_order_created" not in error_by_type,
            str(sorted(error_by_type)),
        )

        latency_rows = telemetry_analysis.latency_by_route(START, END, engine=engine)
        check("latency_by_route is JSON serializable", json.dumps(latency_rows) is not None)
        latency_routes = {row["route_template"]: row for row in latency_rows}
        check(
            "latency_by_route drops rows missing duration_ms",
            "/inventory/products/{id}" not in latency_routes and len(latency_rows) == 2,
            str(latency_rows),
        )
        check(
            "latency_by_route mean for /auth/login is 200",
            latency_routes.get("/auth/login", {}).get("avg_duration_ms") == 200,
            str(latency_routes.get("/auth/login")),
        )

        received_windows: list[tuple[datetime, datetime]] = []

        def tracking_events_per_day(start_date, end_date, *, engine):
            received_windows.append((start_date, end_date))
            return original_events_per_day(start_date, end_date, engine=engine)

        original_events_per_day = telemetry_analysis.events_per_day
        original_error_rate = telemetry_analysis.error_rate_by_type
        original_latency = telemetry_analysis.latency_by_route

        def tracking_error_rate(start_date, end_date, *, engine):
            received_windows.append((start_date, end_date))
            return original_error_rate(start_date, end_date, engine=engine)

        def tracking_latency(start_date, end_date, *, engine):
            received_windows.append((start_date, end_date))
            return original_latency(start_date, end_date, engine=engine)

        telemetry_analysis.events_per_day = tracking_events_per_day
        telemetry_analysis.error_rate_by_type = tracking_error_rate
        telemetry_analysis.latency_by_route = tracking_latency
        try:
            telemetry_analysis.build_telemetry_report(START, END, engine=engine)
        finally:
            telemetry_analysis.events_per_day = original_events_per_day
            telemetry_analysis.error_rate_by_type = original_error_rate
            telemetry_analysis.latency_by_route = original_latency

        check(
            "every metric function receives the same resolved period",
            received_windows == [(START, END)] * 3,
            str(received_windows),
        )

        pipeline_calls = {"count": 0}
        original_build = telemetry_analysis.build_telemetry_report

        def tracking_build(start_date, end_date, *, engine):
            pipeline_calls["count"] += 1
            return original_build(start_date, end_date, engine=engine)

        telemetry_analysis.build_telemetry_report = tracking_build
        telemetry_router.clear_telemetry_report_cache()
        try:
            first_direct = telemetry_router._cached_telemetry_report(START, END)
            second_direct = telemetry_router._cached_telemetry_report(START, END)
            check(
                "direct cache hit does not rerun the analysis pipeline",
                pipeline_calls["count"] == 1,
                str(pipeline_calls),
            )
            check("direct cached payloads match", first_direct == second_direct)

            other_direct = telemetry_router._cached_telemetry_report(START, WINDOW_END_EXCLUSIVE)
            check(
                "a different date window is calculated separately",
                pipeline_calls["count"] == 2,
                str(pipeline_calls),
            )

            cache_key = telemetry_router._report_cache_key(START, END)
            with telemetry_router._report_cache_lock:
                cached = telemetry_router._report_cache.get(cache_key)
                if cached is not None:
                    telemetry_router._report_cache[cache_key] = (time.monotonic() - 1, cached[1])
            expired_direct = telemetry_router._cached_telemetry_report(START, END)
            check(
                "an expired cache entry is recalculated",
                expired_direct["period"]["from"] == first_direct["period"]["from"]
                and pipeline_calls["count"] == 3,
                str(pipeline_calls),
            )

            telemetry_router.clear_telemetry_report_cache()
            pipeline_calls["count"] = 0
            first = client.get(
                "/telemetry/report",
                params={
                    "start_date": "2026-09-01T00:00:00Z",
                    "end_date": "2026-09-03T00:00:00Z",
                },
            )
            second = client.get(
                "/telemetry/report",
                params={
                    "start_date": "2026-09-01T00:00:00Z",
                    "end_date": "2026-09-03T00:00:00Z",
                },
            )
            check("GET /telemetry/report returns HTTP 200", first.status_code == 200, first.text)
            payload = first.json()
            check("response has period.from and period.to", "from" in payload.get("period", {}) and "to" in payload.get("period", {}))
            check(
                "response has metrics object with implemented keys",
                set(payload.get("metrics", {})) == APPROVED_METRIC_KEYS,
                str(payload.get("metrics", {}).keys()),
            )
            check(
                "HTTP cache hit does not rerun the analysis pipeline",
                first.status_code == 200
                and second.status_code == 200
                and pipeline_calls["count"] == 1,
                str(pipeline_calls),
            )
            check("identical cached HTTP payloads match", first.json() == second.json())
        finally:
            telemetry_analysis.build_telemetry_report = original_build
            telemetry_router.clear_telemetry_report_cache()

        default_response = client.get("/telemetry/report")
        check("omitted dates default to HTTP 200", default_response.status_code == 200, default_response.text)
        default_payload = default_response.json()
        default_from = datetime.fromisoformat(default_payload["period"]["from"].replace("Z", "+00:00"))
        default_to = datetime.fromisoformat(default_payload["period"]["to"].replace("Z", "+00:00"))
        check(
            "default period is seven UTC days",
            default_to - default_from == timedelta(days=7),
            str(default_payload["period"]),
        )
        check(
            "default period.to is aligned UTC now",
            abs(default_to - datetime.now(UTC)) < timedelta(seconds=telemetry_router.REPORT_CACHE_TTL_SECONDS + 1),
            str(default_payload["period"]),
        )
        check("cache TTL is 60 seconds", telemetry_router.REPORT_CACHE_TTL_SECONDS == 60)

        invalid = client.get("/telemetry/report", params={"start_date": "not-a-date"})
        check("invalid ISO start_date is rejected", invalid.status_code == 422, invalid.text)
        inverted = client.get(
            "/telemetry/report",
            params={"start_date": END.isoformat(), "end_date": START.isoformat()},
        )
        check("inverted window is rejected", inverted.status_code == 422, inverted.text)

        ingest = client.post("/telemetry/events", json={"events": []})
        check(
            "existing POST /telemetry/events returns persisted batch counts",
            ingest.status_code == 200
            and ingest.json()
            == {
                "received": 0,
                "stored": 0,
                "rejected": 0,
            },
            ingest.text,
        )

    print()
    isolated_failed = bool(failures)
    if isolated_failed:
        print(f"{len(failures)} failure(s): {failures}")
    else:
        print("All HealthCore telemetry report checks passed.")

    try:
        _replay_supplied_export()
    except Exception as exc:
        print()
        print("EXPORT REPLAY (isolated engine; not a live HTTP response from Supabase)")
        print(f"BLOCKED  {type(exc).__name__}: {exc}")

    return 1 if isolated_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
