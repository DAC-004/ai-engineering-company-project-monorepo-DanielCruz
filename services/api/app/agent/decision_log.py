"""Durable action log for one agentic flow.

Each line records what the flow did and why. It does not store the question,
the answer, retrieved text, or any identifier value.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from shared.healthcore_rag.config import REPO_ROOT, runtime_data_path

logger = logging.getLogger(__name__)

DECISION_DIRECTORY = runtime_data_path(
    Path("/var/lib/healthcore/agent-decisions"),
    REPO_ROOT / "data" / "process" / "agent_decisions",
)


def decision_directory() -> Path:
    """Return the gitignored directory for decision records."""
    return DECISION_DIRECTORY


def append_decision(
    *,
    flow: str,
    action: str,
    reason: str,
    route: str,
    trace_id: str = "",
    directory: Path | None = None,
) -> Path:
    """Append one JSON object and return the log path.

    ``trace_id`` is an opaque run id. Callers must not pass question text,
    model output, or a patient or government identifier.
    """
    target = directory or decision_directory()
    target.mkdir(parents=True, exist_ok=True)
    record = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "flow": flow,
        "action": action,
        "reason": reason,
        "route": route,
        "trace_id": trace_id,
    }
    path = target / "decisions.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info(
        "agent_decision flow=%s action=%s reason=%s route=%s",
        flow,
        action,
        reason,
        route,
    )
    return path
