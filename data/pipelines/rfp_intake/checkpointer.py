"""SQLite checkpointer for Part 3. The API path does not use MemorySaver.

Each call opens the same file, compiles a new graph, and closes the connection.
Resume reads the checkpoint from that file, so it is not a restart of an
in-memory graph.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from langgraph.checkpoint.sqlite import SqliteSaver

from data.pipelines.rfp_intake.generation import REPO_ROOT

CHECKPOINT_DIR = REPO_ROOT / "data" / "process" / "rfp_checkpoints"
CHECKPOINT_PATH = CHECKPOINT_DIR / "approvals.sqlite"

T = TypeVar("T")


def thread_id(ticket_id: str, department_id: str | None = None) -> str:
    """Namespace a run by ticket, and a branch by department."""
    if department_id is None:
        return f"rfp-{ticket_id}"
    return f"rfp-{ticket_id}:{department_id}"


def with_checkpointer(path: Path, use: Callable[[SqliteSaver], T]) -> T:
    """Open path, run use, and close the connection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), check_same_thread=False)
    try:
        saver = SqliteSaver(connection)
        saver.setup()
        return use(saver)
    finally:
        connection.close()
