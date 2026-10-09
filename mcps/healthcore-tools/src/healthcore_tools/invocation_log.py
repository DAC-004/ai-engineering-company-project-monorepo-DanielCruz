"""One traceable log record per tool invocation.

The record names the tool, the OAuth client, and the result code. It must not
include the bearer token, the upstream service password, or the raw Authorization
header. Callers pass the client id (or subject) already extracted from verified
claims.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

INVOCATION_LOGGER_NAME = "healthcore_mcp.invocations"

_logger = logging.getLogger(INVOCATION_LOGGER_NAME)


def configure_invocation_logging() -> None:
    """Attach a single stderr handler if the application has not configured logging yet."""
    if _logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = True


def invocation_log_path() -> Path:
    """Return the JSONL path that remains after the process exits.

    ``HEALTHCORE_INVOCATION_LOG`` overrides the default. The line stores the
    tool name, client id, and result code already accepted by the logger.
    """
    override = os.environ.get("HEALTHCORE_INVOCATION_LOG", "").strip()
    if override:
        return Path(override)
    return Path("data/process/mcp_invocations/invocations.jsonl")


def log_tool_invocation(*, tool: str, client: str, result: str) -> None:
    """Record tool, client, and result. `result` is a code such as ok or an ErrorCode."""
    _logger.info("tool=%s client=%s result=%s", tool, client, result)
    path = invocation_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "tool": tool,
        "client": client,
        "result": result,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
