"""DEV-55 contract and runtime validation for the async incident-analysis queue."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]


def _check(failures: list[str], name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"PASS  {name}")
    else:
        failures.append(name)
        print(f"FAIL  {name} {detail}")


def run_contract() -> int:
    """Isolated TestClient checks with eager Celery (no live worker required)."""
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(API_DIR))

    tmpdir = tempfile.mkdtemp(prefix="async-tasks-")
    os.environ["SECRET_KEY"] = "validation-secret-key-32chars!!"
    os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
    os.environ["JWT_ALGORITHM"] = "HS256"
    os.environ["TINYDB_PATH"] = str(Path(tmpdir) / "auth.json")
    os.environ["DATABASE_URL"] = f"sqlite:///{(Path(tmpdir) / 'inventory.db').resolve().as_posix()}"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["INCIDENT_DATA_DIR"] = str(Path(tmpdir) / "incident-data")

    from celery.exceptions import Retry
    from fastapi.testclient import TestClient
    from sqlmodel import Session, select

    from app.core.config import get_settings
    from app.db.database import get_engine, init_databases, reset_engine_for_tests
    from app.db.tinydb import reset_db_for_tests
    from app.main import app
    from app.models import TaskFailure
    from app.task_failures import record_terminal_failure
    from app.tasks import analyze_incidents_task

    get_settings.cache_clear()
    reset_engine_for_tests()
    reset_db_for_tests()
    init_databases()

    sample_csv = REPO_ROOT / "scripts" / "incidents-healthcore.csv"
    fallback = (
        "incident_id,date,clinic_id,country,category,description,status,patient_id,satisfaction_score\n"
        "INC-1,2024-01-15,CL-1,US,CLINICAL,Test description long enough,CLOSED,P-1,5\n"
    )
    csv_bytes = sample_csv.read_bytes() if sample_csv.exists() else fallback.encode("utf-8")

    failures: list[str] = []
    client = TestClient(app)

    client.post(
        "/users",
        json={
            "email": "alice@healthcore.com",
            "password": "SecurePass1!",
            "name": "Alice",
        },
    )
    login = client.post(
        "/auth/login",
        data={"username": "alice@healthcore.com", "password": "SecurePass1!"},
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

    unauth = client.post(
        "/api/incidents/analyze",
        files={"file": ("incidents.csv", csv_bytes, "text/csv")},
    )
    _check(failures, "POST /api/incidents/analyze without token -> 401", unauth.status_code == 401)

    started = time.perf_counter()
    enqueued = client.post(
        "/api/incidents/analyze",
        headers=auth,
        files={"file": ("incidents.csv", csv_bytes, "text/csv")},
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    body = enqueued.json() if enqueued.headers.get("content-type", "").startswith("application/json") else {}
    _check(
        failures,
        "POST /api/incidents/analyze -> 202 task_id",
        enqueued.status_code == 202 and bool(body.get("task_id")),
        enqueued.text,
    )
    print(f"INFO  eager enqueue elapsed_ms={elapsed_ms:.1f} (timing is not a live-worker rubric proof)")

    task_id = body.get("task_id", "")
    unauth_status = client.get(f"/tasks/{task_id or 'missing'}")
    _check(failures, "GET /tasks/{task_id} without token -> 401", unauth_status.status_code == 401)

    status_response = client.get(f"/tasks/{task_id}", headers=auth)
    payload = status_response.json() if status_response.status_code == 200 else {}
    _check(
        failures,
        "GET /tasks/{task_id} success with result",
        status_response.status_code == 200
        and payload.get("status") == "success"
        and payload.get("task_id") == task_id
        and isinstance(payload.get("result"), dict)
        and payload["result"].get("total_records") is not None,
        status_response.text,
    )

    results = client.get("/api/incidents/results", headers=auth)
    _check(
        failures,
        "GET /api/incidents/results after eager analyze",
        results.status_code == 200 and results.json().get("total_records") is not None,
        results.text,
    )

    first = record_terminal_failure(task_id="idempotent-task", attempt=3, error_message="boom")
    second = record_terminal_failure(task_id="idempotent-task", attempt=3, error_message="boom-again")
    with Session(get_engine()) as session:
        rows = list(session.exec(select(TaskFailure).where(TaskFailure.task_id == "idempotent-task")))
    _check(
        failures,
        "TaskFailure insert is idempotent on task_id",
        first is True and second is False and len(rows) == 1,
        f"first={first} second={second} count={len(rows)}",
    )

    retry_raised = False
    retry_when = None
    try:
        analyze_incidents_task.apply(
            args=["missing-upload-id"],
            task_id="retry-missing-upload",
            retries=0,
            throw=True,
        )
    except Retry as exc:
        retry_raised = True
        retry_when = exc.when
    with Session(get_engine()) as session:
        retry_row = session.exec(
            select(TaskFailure).where(TaskFailure.task_id == "retry-missing-upload")
        ).first()
    _check(
        failures,
        "attempt 1 retries with backoff and does not write TaskFailure",
        retry_raised and retry_when not in (None, 0) and retry_row is None,
        f"raised={retry_raised} when={retry_when} row={retry_row}",
    )

    terminal_error = None
    try:
        analyze_incidents_task.apply(
            args=["missing-upload-id"],
            task_id="terminal-missing-upload",
            retries=2,
            throw=True,
        )
    except FileNotFoundError as exc:
        terminal_error = exc
    with Session(get_engine()) as session:
        failure_row = session.exec(
            select(TaskFailure).where(TaskFailure.task_id == "terminal-missing-upload")
        ).first()
    _check(
        failures,
        "attempt 3 is terminal TaskFailure without a fourth retry",
        terminal_error is not None
        and failure_row is not None
        and failure_row.attempt == 3
        and "missing-upload-id" in (failure_row.error_message or ""),
        f"error={terminal_error} row={failure_row}",
    )

    print()
    if failures:
        print(f"{len(failures)} contract failure(s): {failures}")
        return 1
    print("All DEV-55 contract checks passed.")
    return 0


def _runtime_blocked(reason: str) -> int:
    print(f"BLOCKED  runtime validation: {reason}")
    return 2


def run_runtime() -> int:
    """Live Redis/worker/API checks. Does not print secrets from .env."""
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(API_DIR))

    from dotenv import load_dotenv

    load_dotenv(API_DIR / ".env")
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    try:
        import redis
    except ImportError:
        return _runtime_blocked("redis package is not installed")

    client = redis.Redis.from_url(redis_url)
    try:
        pong = client.ping()
    except Exception as exc:
        return _runtime_blocked(f"Redis is not reachable at REDIS_URL ({exc.__class__.__name__})")
    print(f"PASS  Redis ping={pong}")

    try:
        import httpx
    except ImportError:
        return _runtime_blocked("httpx is not installed")

    api_base = os.environ.get("ASYNC_TASKS_API_BASE", "http://127.0.0.1:8000")
    failures: list[str] = []
    with httpx.Client(base_url=api_base, timeout=10.0) as http:
        try:
            health = http.get("/health")
        except Exception as exc:
            return _runtime_blocked(f"API is not reachable at {api_base} ({exc.__class__.__name__})")
        _check(failures, "GET /health", health.status_code == 200, health.text)

        register = http.post(
            "/users",
            json={
                "email": f"async-{int(time.time())}@healthcore.com",
                "password": "SecurePass1!",
                "name": "Async Validator",
            },
        )
        if register.status_code not in (201, 400, 409):
            return _runtime_blocked(f"user registration failed: {register.status_code}")
        email = register.json().get("email") if register.status_code == 201 else None
        if not email:
            email = f"async-{int(time.time())}@healthcore.com"
            http.post(
                "/users",
                json={"email": email, "password": "SecurePass1!", "name": "Async Validator"},
            )
        login = http.post("/auth/login", data={"username": email, "password": "SecurePass1!"})
        if login.status_code != 200:
            return _runtime_blocked(f"login failed: {login.status_code}")
        token = login.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        sample_csv = REPO_ROOT / "scripts" / "incidents-healthcore.csv"
        csv_bytes = sample_csv.read_bytes() if sample_csv.exists() else (
            "incident_id,date,clinic_id,country,category,description,status,patient_id,satisfaction_score\n"
            "INC-1,2024-01-15,CL-1,US,CLINICAL,Test description long enough,CLOSED,P-1,5\n"
        ).encode("utf-8")

        started = time.perf_counter()
        enqueued = http.post(
            "/api/incidents/analyze",
            headers=auth,
            files={"file": ("incidents.csv", csv_bytes, "text/csv")},
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        body = enqueued.json() if enqueued.status_code == 202 else {}
        _check(
            failures,
            "live POST /api/incidents/analyze -> 202 under 200ms",
            enqueued.status_code == 202 and bool(body.get("task_id")) and elapsed_ms < 200,
            f"status={enqueued.status_code} elapsed_ms={elapsed_ms:.1f} body={enqueued.text}",
        )
        print(f"INFO  live enqueue elapsed_ms={elapsed_ms:.1f}")
        task_id = body.get("task_id")
        if not task_id:
            print("BLOCKED  cannot poll task status without task_id")
        else:
            seen: list[str] = []
            result_body = None
            deadline = time.time() + 60
            while time.time() < deadline:
                polled = http.get(f"/tasks/{task_id}", headers=auth)
                if polled.status_code != 200:
                    break
                result_body = polled.json()
                status = result_body.get("status")
                if status not in seen:
                    seen.append(status)
                    print(f"INFO  lifecycle status={status}")
                if status in {"success", "failure"}:
                    break
                time.sleep(0.25)
            _check(
                failures,
                "live GET /tasks/{task_id} reaches success",
                bool(result_body)
                and result_body.get("status") == "success"
                and isinstance(result_body.get("result"), dict),
                f"seen={seen} last={result_body}",
            )

        try:
            flower = httpx.get("http://127.0.0.1:5555/", timeout=5.0)
            _check(
                failures,
                "Flower HTTP responds on port 5555",
                flower.status_code < 500,
                f"status={flower.status_code}",
            )
        except Exception as exc:
            print(f"BLOCKED  Flower HTTP on :5555 ({exc.__class__.__name__})")

    # Enqueue a real missing-upload failure through Celery (not the HTTP API).
    try:
        from app.celery_app import celery_app
        from app.core.config import get_settings
        from app.db.database import get_engine, init_databases
        from app.models import TaskFailure
        from sqlmodel import Session, select

        get_settings.cache_clear()
        init_databases()
        fail_async = celery_app.send_task(
            "app.tasks.analyze_incidents_task",
            args=["missing-upload-id"],
        )
        print(f"INFO  enqueued missing-upload-id task_id={fail_async.id}")
        failure_row = None
        deadline = time.time() + 90
        while time.time() < deadline:
            with Session(get_engine()) as session:
                failure_row = session.exec(
                    select(TaskFailure).where(TaskFailure.task_id == str(fail_async.id))
                ).first()
            if failure_row is not None:
                break
            time.sleep(1)
        _check(
            failures,
            "missing upload_id produced TaskFailure attempt=3",
            failure_row is not None and failure_row.attempt == 3,
            f"row={failure_row}",
        )
    except Exception as exc:
        print(f"BLOCKED  missing-upload DLQ path ({exc.__class__.__name__}: {exc})")

    # Queue occupancy is evidence even when Flower does not render the DLQ.
    queue_keys = []
    for key in client.scan_iter(match="*dead_letter*"):
        queue_keys.append(key.decode() if isinstance(key, bytes) else str(key))
    print(f"INFO  Redis keys matching dead_letter: {queue_keys or '(none yet)'}")
    for key_name in ("dead_letter",):
        try:
            key_type = client.type(key_name)
            decoded_type = key_type.decode() if isinstance(key_type, bytes) else str(key_type)
            length = client.llen(key_name) if decoded_type == "list" else None
            print(f"INFO  Redis {key_name} type={decoded_type} llen={length}")
        except Exception as exc:
            print(f"INFO  Redis {key_name} inspect failed: {exc.__class__.__name__}")

    if failures:
        print(f"{len(failures)} runtime failure(s): {failures}")
        return 1
    print("Runtime checks that could execute completed.")
    return 0


def main() -> int:
    if "--runtime" in sys.argv:
        return run_runtime()
    if "--contract-child" in sys.argv:
        return run_contract()

    child = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--contract-child"],
        cwd=str(API_DIR),
    )
    runtime_code = run_runtime()
    if child.returncode != 0:
        return child.returncode
    if runtime_code == 2:
        print("Contract passed. Runtime validation is blocked until Redis/API/worker are up.")
        return 0
    return runtime_code


if __name__ == "__main__":
    raise SystemExit(main())
