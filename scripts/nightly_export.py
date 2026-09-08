#!/usr/bin/env python3
"""Independent nightly telemetry export and pipeline trigger (Ticket #DEV-53).

Usage (from repository root):

    python scripts/nightly_export.py

Optional:

    TARGET_DATE=YYYY-MM-DD python scripts/nightly_export.py

This process does not import FastAPI, APScheduler, or application lifespan
hooks. The sole production trigger is OS crontab (see infra/cron/nightly-export.crontab).
"""

from __future__ import annotations

import csv
import json
import logging
import os
import shlex
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_DIR = REPO_ROOT / "services" / "api"
for _path in (str(REPO_ROOT), str(API_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from sqlmodel import Session, select  # noqa: E402

from app.db.database import get_engine, init_databases  # noqa: E402
from app.models import JobRun, JobRunStatus, TelemetryEventRecord  # noqa: E402
from services.job_runner import (  # noqa: E402
    NIGHTLY_JOB_NAME,
    ClaimOutcome,
    claim_nightly_run,
    ensure_not_processing,
    mark_completed,
    mark_failed,
)

CSV_COLUMNS = (
    "event_id",
    "timestamp",
    "session_id",
    "user_id",
    "event_type",
    "schema_version",
    "request_id",
    "tags",
)
RAW_DIR = REPO_ROOT / "data" / "raw"
LOG_PATH = RAW_DIR / "nightly_export.log"
PIPELINE_ENTRYPOINT = REPO_ROOT / "data" / "pipelines" / "pipeline.py"

logger = logging.getLogger("nightly_export")


class JobLogFilter(logging.Filter):
    """Guarantee timestamped lines include job_name and resulting status."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "job_name"):
            record.job_name = NIGHTLY_JOB_NAME
        if not hasattr(record, "status"):
            record.status = "unknown"
        return True


def configure_logging() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s job_name=%(job_name)s status=%(status)s %(message)s"
    )
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.addFilter(JobLogFilter())
    logger.propagate = False


def log_event(level: int, message: str, status: str) -> None:
    logger.log(level, message, extra={"job_name": NIGHTLY_JOB_NAME, "status": status})


def resolve_target_date(raw_value: str | None = None) -> date:
    """Use TARGET_DATE=YYYY-MM-DD or the previous calendar day in UTC."""
    value = raw_value if raw_value is not None else os.environ.get("TARGET_DATE")
    if value is None or value.strip() == "":
        return datetime.now(timezone.utc).date() - timedelta(days=1)
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("TARGET_DATE must use YYYY-MM-DD") from exc


def csv_path_for(target_date: date) -> Path:
    return RAW_DIR / f"telemetry_{target_date.isoformat()}.csv"


def utc_day_window(target_date: date) -> tuple[datetime, datetime]:
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=UTC)
    return start, start + timedelta(days=1)


def _serialize_tags(tags: object) -> str:
    if tags is None:
        return "{}"
    if isinstance(tags, str):
        return tags
    return json.dumps(tags, separators=(",", ":"), default=str)


def export_telemetry_csv(session: Session, target_date: date, output_path: Path) -> int:
    """Write telemetry_events for target_date. Never overwrite an existing CSV.

    An empty date still produces a header-only backup. The CSV is an audit copy
    and is not pipeline input.
    """
    if output_path.exists():
        log_event(
            logging.INFO,
            f"CSV backup already exists; leaving {output_path.name} unchanged",
            JobRunStatus.processing.value,
        )
        return 0

    window_start, window_end = utc_day_window(target_date)
    statement = (
        select(TelemetryEventRecord)
        .where(
            TelemetryEventRecord.timestamp >= window_start,
            TelemetryEventRecord.timestamp < window_end,
        )
        .order_by(TelemetryEventRecord.timestamp, TelemetryEventRecord.event_id)
    )
    rows = list(session.exec(statement).all())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        for record in rows:
            writer.writerow(
                {
                    "event_id": record.event_id,
                    "timestamp": record.timestamp.isoformat()
                    if isinstance(record.timestamp, datetime)
                    else str(record.timestamp),
                    "session_id": record.session_id,
                    "user_id": record.user_id or "",
                    "event_type": record.event_type,
                    "schema_version": record.schema_version,
                    "request_id": record.request_id,
                    "tags": _serialize_tags(record.tags),
                }
            )
    log_event(
        logging.INFO,
        f"Exported {len(rows)} telemetry_events rows to {output_path.name}",
        JobRunStatus.processing.value,
    )
    return len(rows)


def default_pipeline_command() -> list[str]:
    """Actual Milestone 6 CLI: python data/pipelines/pipeline.py (not the ticket sample)."""
    return [sys.executable, str(PIPELINE_ENTRYPOINT)]


def resolve_pipeline_command() -> list[str]:
    """Production always uses the Milestone 6 CLI.

    NIGHTLY_EXPORT_PIPELINE_COMMAND is a validation-only override. It is ignored
    unless NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE=1, so an incidental production
    environment value cannot silently replace the real pipeline.
    """
    override = os.environ.get("NIGHTLY_EXPORT_PIPELINE_COMMAND")
    allow_override = os.environ.get("NIGHTLY_EXPORT_ALLOW_PIPELINE_OVERRIDE", "").strip() == "1"
    if override is None or override.strip() == "" or not allow_override:
        return default_pipeline_command()
    stripped = override.strip()
    if stripped.startswith("["):
        parsed = json.loads(stripped)
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ValueError("NIGHTLY_EXPORT_PIPELINE_COMMAND JSON must be a list of strings")
        return parsed
    return shlex.split(stripped, posix=os.name != "nt")


def trigger_pipeline() -> None:
    """Run the existing data pipeline as a subprocess after CSV export."""
    command = resolve_pipeline_command()
    log_event(
        logging.INFO,
        "Triggering data pipeline subprocess: " + " ".join(command),
        JobRunStatus.processing.value,
    )
    env = os.environ.copy()
    pythonpath = [str(REPO_ROOT), str(API_DIR)]
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.stdout:
        logger.info(
            completed.stdout.strip(),
            extra={"job_name": NIGHTLY_JOB_NAME, "status": JobRunStatus.processing.value},
        )
    if completed.returncode != 0:
        stderr_text = (completed.stderr or "").strip()
        raise RuntimeError(
            f"Pipeline subprocess exited {completed.returncode}"
            + (f": {stderr_text[:500]}" if stderr_text else "")
        )


def _error_text(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _load_run(session: Session, run_id: int) -> JobRun:
    run = session.get(JobRun, run_id)
    if run is None:
        raise RuntimeError(f"job_runs row id={run_id} disappeared")
    return run


def _fail_claimed_run(engine, run_id: int, resolved: date, exc: BaseException) -> None:
    """Persist failed status for a claimed run. Best-effort if the DB is unavailable."""
    try:
        with Session(engine) as session:
            mark_failed(session, _load_run(session, run_id), _error_text(exc))
    except Exception as cleanup_exc:
        log_event(
            logging.ERROR,
            f"Unable to mark job_runs id={run_id} failed: {_error_text(cleanup_exc)}",
            JobRunStatus.failed.value,
        )
    log_event(
        logging.ERROR,
        f"Nightly export failed for target_date={resolved.isoformat()}: {_error_text(exc)}",
        JobRunStatus.failed.value,
    )


def _cleanup_claimed_run(engine, run_id: int) -> None:
    """finally-guard: never leave the claimed row in processing."""
    try:
        with Session(engine) as session:
            ensure_not_processing(
                session,
                _load_run(session, run_id),
                "execution ended while processing",
            )
    except Exception as cleanup_exc:
        log_event(
            logging.ERROR,
            f"Unable to clear processing for job_runs id={run_id}: {_error_text(cleanup_exc)}",
            JobRunStatus.failed.value,
        )


def run_nightly_export(target_date: date | None = None) -> int:
    """Execute one nightly orchestration cycle. Returns a process exit code."""
    configure_logging()
    resolved = target_date if target_date is not None else resolve_target_date()
    log_event(
        logging.INFO,
        f"Starting nightly export for target_date={resolved.isoformat()}",
        JobRunStatus.pending.value,
    )

    init_databases()
    engine = get_engine()
    run_id: int | None = None
    try:
        with Session(engine) as session:
            claim = claim_nightly_run(session, resolved)
            if claim.outcome == ClaimOutcome.duplicate:
                log_event(
                    logging.INFO,
                    f"Skipped duplicate nightly_export for target_date={resolved.isoformat()}",
                    JobRunStatus.completed.value,
                )
                return 0
            if claim.outcome == ClaimOutcome.locked:
                log_event(
                    logging.INFO,
                    "Cancelled: another nightly_export instance already holds processing",
                    JobRunStatus.processing.value,
                )
                return 0
            run = claim.run
            if run is None or run.id is None:
                log_event(logging.ERROR, "Claim succeeded without a job_runs row", "failed")
                return 1
            run_id = run.id

        log_event(
            logging.INFO,
            f"job_runs id={run_id} entered processing for target_date={resolved.isoformat()}",
            JobRunStatus.processing.value,
        )
        # CSV uses a short session so the processing lock stays visible to
        # concurrent workers during the pipeline subprocess.
        with Session(engine) as session:
            export_telemetry_csv(session, resolved, csv_path_for(resolved))
        trigger_pipeline()
        with Session(engine) as session:
            mark_completed(session, _load_run(session, run_id))
        log_event(
            logging.INFO,
            f"Finished nightly export for target_date={resolved.isoformat()}",
            JobRunStatus.completed.value,
        )
        return 0
    except Exception as exc:
        if run_id is not None:
            _fail_claimed_run(engine, run_id, resolved, exc)
        else:
            log_event(
                logging.ERROR,
                f"Nightly export failed for target_date={resolved.isoformat()}: {_error_text(exc)}",
                JobRunStatus.failed.value,
            )
        return 1
    finally:
        if run_id is not None:
            _cleanup_claimed_run(engine, run_id)


def main() -> int:
    """CLI entry. Invalid TARGET_DATE fails before a processing row exists."""
    try:
        return run_nightly_export()
    except Exception as exc:
        configure_logging()
        log_event(logging.ERROR, f"Unhandled nightly export error: {_error_text(exc)}", "failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
