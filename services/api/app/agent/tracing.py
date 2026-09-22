"""Persist and reload structured traces for support-agent runs.

Console logging is not a trace. Each run writes one JSON file that can be
loaded by ``trace_id`` after ``run_support_agent`` returns.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.healthcore_rag.config import REPO_ROOT

TRACE_DIRECTORY = REPO_ROOT / "data" / "process" / "agent_traces"


def trace_directory() -> Path:
    """Return the gitignored directory for runtime trace files."""
    return TRACE_DIRECTORY


def _safe_trace_id(trace_id: str) -> str:
    """Reject ids that could escape the trace directory."""
    if not trace_id or Path(trace_id).name != trace_id:
        raise ValueError("trace_id must be a single path segment.")
    if "/" in trace_id or "\\" in trace_id:
        raise ValueError("trace_id must be a single path segment.")
    return trace_id


def persist_trace(trace: dict[str, Any], trace_dir: Path | None = None) -> Path:
    """Write one trace JSON file and return its path."""
    directory = trace_dir or trace_directory()
    directory.mkdir(parents=True, exist_ok=True)
    trace_id = _safe_trace_id(str(trace["trace_id"]))
    trace_path = directory / f"{trace_id}.json"
    trace_path.write_text(
        json.dumps(trace, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return trace_path


def load_trace(trace_id: str, trace_dir: Path | None = None) -> dict[str, Any]:
    """Load a previously stored trace. Raises if that id was not persisted."""
    directory = trace_dir or trace_directory()
    safe_id = _safe_trace_id(trace_id)
    trace_path = directory / f"{safe_id}.json"
    if not trace_path.is_file():
        raise FileNotFoundError(f"No agent trace is stored for trace_id {safe_id}.")
    loaded = json.loads(trace_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Stored agent trace {safe_id} is not a JSON object.")
    return loaded
