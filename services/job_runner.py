"""Create, query, and update job_runs for the independent nightly export process.

This module is the status-control service for Ticket #DEV-53. It does not import
FastAPI, APScheduler, or application lifespan hooks. pipeline_runs remains the
ETL control table and is never written here.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

API_DIR = Path(__file__).resolve().parent / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.models import JobRun, JobRunStatus  # noqa: E402

NIGHTLY_JOB_NAME = "nightly_export"


class ClaimOutcome(str, Enum):
    """Result of trying to start a nightly_export run for one target_date."""

    claimed = "claimed"
    duplicate = "duplicate"
    locked = "locked"


@dataclass(frozen=True)
class ClaimResult:
    outcome: ClaimOutcome
    run: JobRun | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def has_processing_lock(
    session: Session,
    job_name: str = NIGHTLY_JOB_NAME,
    exclude_id: int | None = None,
) -> bool:
    """True when another job_runs row already holds the processing lock."""
    statement = select(JobRun).where(
        JobRun.job_name == job_name,
        JobRun.status == JobRunStatus.processing.value,
    )
    if exclude_id is not None:
        statement = statement.where(JobRun.id != exclude_id)
    return session.exec(statement).first() is not None


def has_completed_for_date(
    session: Session,
    target_date: date,
    job_name: str = NIGHTLY_JOB_NAME,
) -> bool:
    """True when this job_name already completed for the given UTC calendar day."""
    statement = select(JobRun).where(
        JobRun.job_name == job_name,
        JobRun.target_date == target_date,
        JobRun.status == JobRunStatus.completed.value,
    )
    return session.exec(statement).first() is not None


def create_pending_run(
    session: Session,
    target_date: date,
    job_name: str = NIGHTLY_JOB_NAME,
) -> JobRun:
    """Insert a pending row before any export or pipeline work starts."""
    run = JobRun(
        job_name=job_name,
        target_date=target_date,
        status=JobRunStatus.pending.value,
        created_at=_now(),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def mark_processing(session: Session, run: JobRun) -> JobRun:
    """Move pending -> processing. IntegrityError means the lock is held."""
    run.status = JobRunStatus.processing.value
    run.started_at = _now()
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def mark_completed(session: Session, run: JobRun) -> JobRun:
    run.status = JobRunStatus.completed.value
    run.finished_at = _now()
    run.error_message = None
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def mark_failed(session: Session, run: JobRun, error_message: str) -> JobRun:
    """Record failure. A failed execution must never remain in processing."""
    run.status = JobRunStatus.failed.value
    run.finished_at = _now()
    run.error_message = error_message[:2000]
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def get_run(session: Session, run_id: int) -> JobRun | None:
    return session.get(JobRun, run_id)


def claim_nightly_run(session: Session, target_date: date) -> ClaimResult:
    """Create pending, then take the processing lock, or skip without work.

    Duplicate: a completed nightly_export row already exists for target_date.
    Locked: another nightly_export row is already processing.
    Claimed: this process now holds processing and may export and trigger.

    The unique partial index on (job_name) WHERE status='processing' makes the
    lock exclusive across concurrent processes. That index enforces the
    prescribed processing status; it is not a separate lock table or column.
    """
    if has_completed_for_date(session, target_date):
        return ClaimResult(ClaimOutcome.duplicate)

    if has_processing_lock(session):
        return ClaimResult(ClaimOutcome.locked)

    run = create_pending_run(session, target_date)

    if has_processing_lock(session, exclude_id=run.id):
        session.delete(run)
        session.commit()
        return ClaimResult(ClaimOutcome.locked)

    try:
        return ClaimResult(ClaimOutcome.claimed, mark_processing(session, run))
    except IntegrityError:
        session.rollback()
        stale = get_run(session, run.id) if run.id is not None else None
        if stale is not None and stale.status == JobRunStatus.pending.value:
            session.delete(stale)
            session.commit()
        return ClaimResult(ClaimOutcome.locked)


def ensure_not_processing(session: Session, run: JobRun, error_message: str) -> JobRun:
    """finally-guard: never leave the claimed row in processing after an exit."""
    session.refresh(run)
    if run.status == JobRunStatus.processing.value:
        return mark_failed(session, run, error_message)
    return run
