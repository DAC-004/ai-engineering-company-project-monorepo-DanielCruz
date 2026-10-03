"""In-process guardrail counts. Log lines name the guard, never the user text."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_COUNTS: dict[str, dict[str, int]] = {}


def record(guardrail: str, action: str, failure_type: str) -> None:
    """Count one block or redirect and log only structural fields."""
    logger.info(
        "guardrail=%s action=%s failure_type=%s",
        guardrail,
        action,
        failure_type,
    )
    with _LOCK:
        bucket = _COUNTS.setdefault(guardrail, {})
        bucket[action] = bucket.get(action, 0) + 1
        kinds = _COUNTS.setdefault("failure_type", {})
        kinds[failure_type] = kinds.get(failure_type, 0) + 1


def summary() -> dict[str, dict[str, int]]:
    """Return a copy of the counts for this process."""
    with _LOCK:
        return {name: dict(counts) for name, counts in _COUNTS.items()}


def reset() -> None:
    """Clear counts so one test session does not inherit another."""
    with _LOCK:
        _COUNTS.clear()
