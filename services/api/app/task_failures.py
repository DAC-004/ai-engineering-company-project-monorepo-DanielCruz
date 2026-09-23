"""Insert-once terminal failure rows used as DLQ publication guards."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db.database import get_engine
from app.models import TaskFailure

_ERROR_MESSAGE_MAX = 4000


def record_terminal_failure(*, task_id: str, attempt: int, error_message: str) -> bool:
    """
    Persist the first terminal failure for task_id.

    Returns True when this caller created the row. A unique constraint plus
    IntegrityError handling prevents duplicate rows when acks_late redelivers
    the same failed task. Callers must publish to the DLQ only when this
    returns True so redelivery cannot enqueue a second dead-letter message.
    """
    trimmed = error_message[:_ERROR_MESSAGE_MAX]
    with Session(get_engine()) as session:
        existing = session.exec(
            select(TaskFailure).where(TaskFailure.task_id == task_id)
        ).first()
        if existing is not None:
            return False
        session.add(
            TaskFailure(
                task_id=task_id,
                attempt=attempt,
                error_message=trimmed,
                timestamp=datetime.now(UTC),
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return False
    return True
