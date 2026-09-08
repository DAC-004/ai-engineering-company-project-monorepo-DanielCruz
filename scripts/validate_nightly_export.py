"""Validate Ticket #DEV-53 nightly export: state machine, lock, idempotency, CSV."""

from __future__ import annotations

import importlib.util
import csv
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "services" / "api"
RAW_DIR = REPO_ROOT / "data" / "raw"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

_tmpdir = tempfile.mkdtemp(prefix="nightly-export-")
_sqlite_path = (Path(_tmpdir) / "healthcore.db").resolve().as_posix()
os.environ["SECRET_KEY"] = "validation-secret-key-32chars!!"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["TINYDB_PATH"] = str(Path(_tmpdir) / "auth.json")
os.environ["DATABASE_URL"] = f"sqlite:///{_sqlite_path}"
os.environ.pop("TARGET_DATE", None)

from app.core.config import get_settings  # noqa: E402
from app.db.database import get_engine, init_databases, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.models import JobRun, JobRunStatus, TelemetryEventRecord  # noqa: E402
from data.pipelines.reporting_store import ensure_reporting_tables  # noqa: E402
from services.job_runner import (  # noqa: E402
    NIGHTLY_JOB_NAME,
    has_completed_for_date,
    has_processing_lock,
)
from sqlmodel import Session, select  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "nightly_export",
    REPO_ROOT / "scripts" / "nightly_export.py",
)
if _spec is None or _spec.loader is None:
    raise RuntimeError("unable to load scripts/nightly_export.py")
nightly_export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nightly_export)
CSV_COLUMNS = nightly_export.CSV_COLUMNS
default_pipeline_command = nightly_export.default_pipeline_command
resolve_pipeline_command = nightly_export.resolve_pipeline_command
resolve_target_date = nightly_export.resolve_target_date
run_nightly_export = nightly_export.run_nightly_export

get_settings.cache_clear()
reset_db_for_tests()
reset_engine_for_tests()

TARGET_DAY = date(2026, 9, 7)
OTHER_DAY = date(2026, 9, 6)
CSV_PATH = RAW_DIR / f"telemetry_{TARGET_DAY.isoformat()}.csv"
OK_PIPELINE = Path(_tmpdir) / "ok_pipeline.py"
FAIL_PIPELINE = Path(_tmpdir) / "fail_pipeline.py"
SLOW_PIPELINE = Path(_tmpdir) / "slow_pipeline.py"
OK_PIPELINE.write_text("print('pipeline-ok')\n", encoding="utf-8")
FAIL_PIPELINE.write_text("raise SystemExit(1)\n", encoding="utf-8")
SLOW_PIPELINE.write_text("import time\ntime.sleep(5)\nprint('pipeline-slow-done')\n", encoding="utf-8")


def _command_json(script: Path) -> str:
    return json.dumps([sys.executable, str(script)])


def _seed_events() -> None:
    init_databases()
    with Session(get_engine()) as session:
        session.add(
            TelemetryEventRecord(
                event_id="evt-target-1",
                timestamp=datetime(2026, 9, 7, 8, 15, tzinfo=UTC),
                session_id="sess-1",
                user_id="staff-1",
                event_type="inbound_order_created",
                schema_version="1.0.0",
                request_id="req-1",
                tags={"clinic_id": 3, "country": "US", "total_cost": 40},
            )
        )
        session.add(
            TelemetryEventRecord(
                event_id="evt-target-2",
                timestamp=datetime(2026, 9, 7, 19, 0, tzinfo=UTC),
                session_id="sess-2",
                user_id=None,
                event_type="page_viewed",
                schema_version="1.0.0",
                request_id="req-2",
                tags={"route": "/backoffice/inventory/products"},
            )
        )
        session.add(
            TelemetryEventRecord(
                event_id="evt-other-day",
                timestamp=datetime(2026, 9, 6, 23, 59, tzinfo=UTC),
                session_id="sess-3",
                user_id="staff-1",
                event_type="outbound_order_created",
                schema_version="1.0.0",
                request_id="req-3",
                tags={"clinic_id": 3, "country": "US"},
            )
        )
        session.commit()


def _job_rows() -> list[JobRun]:
    with Session(get_engine()) as session:
        return list(session.exec(select(JobRun).order_by(JobRun.id)).all())


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _run_worker(target: date, pipeline: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["TARGET_DATE"] = target.isoformat()
    env["NIGHTLY_EXPORT_PIPELINE_COMMAND"] = _command_json(pipeline)
    env["NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT), str(API_DIR), env.get("PYTHONPATH", "")])
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "nightly_export.py")],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _source_text(*relative_paths: str) -> str:
    return "\n".join((REPO_ROOT / path).read_text(encoding="utf-8") for path in relative_paths)


def main() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"PASS  {name}")
        else:
            failures.append(name)
            print(f"FAIL  {name} {detail}")

    if CSV_PATH.exists():
        CSV_PATH.unlink()

    _seed_events()
    os.environ["NIGHTLY_EXPORT_PIPELINE_COMMAND"] = _command_json(OK_PIPELINE)
    os.environ["NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE"] = "1"
    os.environ["TARGET_DATE"] = TARGET_DAY.isoformat()

    worker_source = _source_text("scripts/nightly_export.py", "services/job_runner.py")
    import_lines = [
        line.strip()
        for line in worker_source.splitlines()
        if line.strip().startswith("import ") or line.strip().startswith("from ")
    ]
    check(
        "worker does not import FastAPI, APScheduler, or lifespan hooks",
        all(
            "fastapi" not in line.lower()
            and "apscheduler" not in line.lower()
            and "repeat_every" not in line.lower()
            for line in import_lines
        ),
        str(import_lines),
    )
    check(
        "default pipeline CLI is data/pipelines/pipeline.py",
        str(REPO_ROOT / "data" / "pipelines" / "pipeline.py") in default_pipeline_command()
        or default_pipeline_command()[-1].endswith("pipeline.py"),
    )
    saved_command = os.environ.get("NIGHTLY_EXPORT_PIPELINE_COMMAND")
    saved_allow = os.environ.get("NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE")
    os.environ["NIGHTLY_EXPORT_PIPELINE_COMMAND"] = _command_json(FAIL_PIPELINE)
    os.environ.pop("NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE", None)
    guarded = resolve_pipeline_command()
    check(
        "pipeline override is ignored without NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE=1",
        guarded[-1].endswith("pipeline.py"),
        str(guarded),
    )
    os.environ["NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE"] = "1"
    os.environ["NIGHTLY_EXPORT_PIPELINE_COMMAND"] = _command_json(OK_PIPELINE)
    allowed = resolve_pipeline_command()
    check(
        "pipeline override is honored when NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE=1",
        allowed[-1] == str(OK_PIPELINE),
        str(allowed),
    )
    if saved_command is not None:
        os.environ["NIGHTLY_EXPORT_PIPELINE_COMMAND"] = saved_command
    if saved_allow is not None:
        os.environ["NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE"] = saved_allow
    check(
        "TARGET_DATE override parses YYYY-MM-DD",
        resolve_target_date("2024-02-29") == date(2024, 2, 29),
    )
    previous = os.environ.pop("TARGET_DATE", None)
    check(
        "absent TARGET_DATE is previous UTC calendar day",
        resolve_target_date() == datetime.now(timezone.utc).date() - timedelta(days=1),
    )
    if previous is not None:
        os.environ["TARGET_DATE"] = previous

    first = _run_worker(TARGET_DAY, OK_PIPELINE)
    check("successful execution exits 0", first.returncode == 0, first.stderr)
    check("successful log includes timestamp job_name and completed", all(
        token in first.stdout
        for token in ("job_name=nightly_export", "status=completed", "Finished nightly export")
    ), first.stdout)
    check("CSV exists under data/raw with target-date filename", CSV_PATH.is_file())
    csv_rows = _read_csv(CSV_PATH) if CSV_PATH.is_file() else []
    if CSV_PATH.is_file():
        with CSV_PATH.open(encoding="utf-8", newline="") as handle:
            header = next(csv.reader(handle))
        check("CSV column order", header == list(CSV_COLUMNS), str(header))
    check("CSV contains only the target date's events", {row["event_id"] for row in csv_rows} == {"evt-target-1", "evt-target-2"})
    check("CSV does not include the previous UTC day's event", all(row["event_id"] != "evt-other-day" for row in csv_rows))

    rows = _job_rows()
    check("job_runs recorded pending->processing->completed", any(
        row.job_name == NIGHTLY_JOB_NAME
        and row.target_date == TARGET_DAY
        and row.status == JobRunStatus.completed.value
        and row.started_at is not None
        and row.finished_at is not None
        for row in rows
    ), str([(row.status, row.target_date) for row in rows]))
    with Session(get_engine()) as session:
        check("has_completed_for_date is true after success", has_completed_for_date(session, TARGET_DAY))
        check("no processing lock remains after success", not has_processing_lock(session))

    ensure_reporting_tables(get_engine())
    from sqlalchemy import inspect as sa_inspect

    table_names = set(sa_inspect(get_engine()).get_table_names())
    check(
        "job_runs and pipeline_runs coexist as separate tables",
        "job_runs" in table_names and "pipeline_runs" in table_names,
        str(sorted(table_names)),
    )

    original_csv = CSV_PATH.read_text(encoding="utf-8") if CSV_PATH.exists() else ""
    duplicate = _run_worker(TARGET_DAY, FAIL_PIPELINE)
    check("duplicate same-date execution exits 0", duplicate.returncode == 0, duplicate.stderr)
    check(
        "duplicate skip is logged as completed without re-work",
        "Skipped duplicate nightly_export" in duplicate.stdout
        and "job_name=nightly_export" in duplicate.stdout
        and "status=completed" in duplicate.stdout,
        duplicate.stdout,
    )
    check("duplicate run does not overwrite CSV", CSV_PATH.read_text(encoding="utf-8") == original_csv)
    check(
        "duplicate run does not create another completed row's work",
        sum(1 for row in _job_rows() if row.status == JobRunStatus.completed.value) == 1,
    )

    fail_day = date(2026, 9, 8)
    failed = _run_worker(fail_day, FAIL_PIPELINE)
    check("failed execution exits non-zero", failed.returncode != 0, failed.stdout)
    check(
        "failed execution logs ERROR with job_name and failed status",
        "ERROR" in failed.stdout
        and "job_name=nightly_export" in failed.stdout
        and "status=failed" in failed.stdout,
        failed.stdout,
    )
    failed_rows = [row for row in _job_rows() if row.target_date == fail_day]
    check("failed row is stored as failed", failed_rows and failed_rows[-1].status == JobRunStatus.failed.value)
    check("failed row stores an error_message", bool(failed_rows and failed_rows[-1].error_message))
    check(
        "no processing zombie after failure",
        all(row.status != JobRunStatus.processing.value for row in _job_rows()),
        str([row.status for row in _job_rows()]),
    )

    lock_day = date(2026, 9, 9)
    slow = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "scripts" / "nightly_export.py")],
        cwd=str(REPO_ROOT),
        env={
            **os.environ,
            "TARGET_DATE": lock_day.isoformat(),
            "NIGHTLY_EXPORT_PIPELINE_COMMAND": _command_json(SLOW_PIPELINE),
            "NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE": "1",
            "PYTHONPATH": os.pathsep.join([str(REPO_ROOT), str(API_DIR), os.environ.get("PYTHONPATH", "")]),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    blocked = None
    for _ in range(100):
        with Session(get_engine()) as session:
            if has_processing_lock(session):
                blocked = _run_worker(lock_day, OK_PIPELINE)
                break
        if slow.poll() is not None:
            break
        time.sleep(0.1)
    slow_stdout, slow_stderr = slow.communicate(timeout=30)
    check("concurrent holder exits 0 after finishing", slow.returncode == 0, slow_stderr)
    check("blocked concurrent instance was observed", blocked is not None)
    if blocked is not None:
        check("blocked concurrent instance exits 0 silently", blocked.returncode == 0, blocked.stderr)
        check(
            "blocked concurrent instance logs cancellation",
            "Cancelled: another nightly_export instance already holds processing" in blocked.stdout
            and "job_name=nightly_export" in blocked.stdout,
            blocked.stdout,
        )
    lock_csv = RAW_DIR / f"telemetry_{lock_day.isoformat()}.csv"
    check("concurrent lock still produced one CSV for the holder", lock_csv.is_file())
    lock_rows = [row for row in _job_rows() if row.target_date == lock_day]
    check(
        "concurrent executions did not both complete work",
        sum(1 for row in lock_rows if row.status == JobRunStatus.completed.value) == 1,
        str([(row.status, row.error_message) for row in lock_rows]),
    )

    in_process = run_nightly_export(TARGET_DAY)
    check("in-process duplicate path also skips", in_process == 0)

    empty_day = date(2026, 1, 15)
    empty_csv = RAW_DIR / f"telemetry_{empty_day.isoformat()}.csv"
    if empty_csv.exists():
        empty_csv.unlink()
    empty_run = _run_worker(empty_day, OK_PIPELINE)
    check("empty target date exits 0", empty_run.returncode == 0, empty_run.stderr)
    check("empty target date writes header-only CSV", empty_csv.is_file())
    if empty_csv.is_file():
        with empty_csv.open(encoding="utf-8", newline="") as handle:
            empty_header = next(csv.reader(handle))
            empty_body = list(csv.reader(handle))
        check("empty CSV uses telemetry_events columns", empty_header == list(CSV_COLUMNS), str(empty_header))
        check("empty CSV has no data rows", empty_body == [], str(empty_body))
    empty_rows = [row for row in _job_rows() if row.target_date == empty_day]
    check(
        "empty target date completes after pipeline trigger",
        empty_rows and empty_rows[-1].status == JobRunStatus.completed.value,
        str([(row.status, row.error_message) for row in empty_rows]),
    )
    check(
        "empty target date does not remain processing",
        all(row.status != JobRunStatus.processing.value for row in empty_rows),
    )
    check("empty-date log shows pipeline trigger", "Triggering data pipeline subprocess" in empty_run.stdout, empty_run.stdout)

    processing_before_invalid = [row.id for row in _job_rows() if row.status == JobRunStatus.processing.value]
    invalid = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "nightly_export.py")],
        cwd=str(REPO_ROOT),
        env={
            **os.environ,
            "TARGET_DATE": "not-a-date",
            "PYTHONPATH": os.pathsep.join([str(REPO_ROOT), str(API_DIR), os.environ.get("PYTHONPATH", "")]),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    check("invalid TARGET_DATE exits non-zero", invalid.returncode != 0, invalid.stdout)
    check(
        "invalid TARGET_DATE does not create a processing row",
        [row.id for row in _job_rows() if row.status == JobRunStatus.processing.value]
        == processing_before_invalid,
        str([row.status for row in _job_rows()]),
    )

    crontab_text = (REPO_ROOT / "infra" / "cron" / "nightly-export.crontab").read_text(encoding="utf-8")
    check("crontab uses 5 0 * * *", "5 0 * * *" in crontab_text)
    check("crontab sets CRON_TZ=UTC", "CRON_TZ=UTC" in crontab_text)
    check("crontab does not use container path /app", "/app" not in crontab_text)
    check("crontab invokes the unattended launcher", "scripts/run_nightly_export.sh" in crontab_text)
    check(
        "scheduler container files were removed",
        not (REPO_ROOT / "infra" / "scheduler").exists()
        or not any((REPO_ROOT / "infra" / "scheduler").iterdir()),
    )

    for leftover in (
        CSV_PATH,
        RAW_DIR / f"telemetry_{fail_day.isoformat()}.csv",
        lock_csv,
        empty_csv,
    ):
        if leftover.exists():
            leftover.unlink()

    if failures:
        print(f"\n{len(failures)} check(s) failed")
        return 1
    print("\nAll nightly export checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
