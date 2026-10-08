"""Reproducible runtime-path check.

This file is a new check. It does not reconstruct the script that printed
SELECTION_CHECKS_PASSED.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

APP_ROOT = Path("/opt/healthcore/app")
sys.path.insert(0, str(APP_ROOT))

from app.agent.graph import CHECKPOINT_DATABASE
from app.agent.memory_store import MEMORY_DATABASE
from app.agent.tracing import TRACE_DIRECTORY
from data.pipelines.rfp_intake.checkpointer import CHECKPOINT_DIR, CHECKPOINT_PATH

MARKER = "audit-path-probe-20261006"
HOST_PREFIX = "/var/lib/healthcore/"


def main() -> int:
    selected = {
        "CHECKPOINT_DATABASE": CHECKPOINT_DATABASE,
        "TRACE_DIRECTORY": TRACE_DIRECTORY,
        "MEMORY_DATABASE": MEMORY_DATABASE,
        "CHECKPOINT_DIR": CHECKPOINT_DIR,
        "CHECKPOINT_PATH": CHECKPOINT_PATH,
    }
    unexpected = False
    for name, path in selected.items():
        print(f"CONSTANT {name} {path}")
        if not str(path).startswith(HOST_PREFIX):
            unexpected = True
            print(f"UNEXPECTED {name}")

    TRACE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    trace_path = TRACE_DIRECTORY / "audit-path-probe-20261006.json"
    trace_path.write_text(
        json.dumps({"probe": MARKER}),
        encoding="utf-8",
    )
    readback = json.loads(trace_path.read_text(encoding="utf-8"))["probe"]
    print("TRACE_WRITE", trace_path)
    print("TRACE_READBACK", readback)
    if readback != MARKER:
        unexpected = True

    for database_path in (CHECKPOINT_DATABASE, MEMORY_DATABASE, CHECKPOINT_PATH):
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        try:
            connection.execute(
                "create table if not exists audit_path_probe_20261006 (marker text)"
            )
            connection.execute("delete from audit_path_probe_20261006")
            connection.execute(
                "insert into audit_path_probe_20261006 (marker) values (?)",
                (MARKER,),
            )
            connection.commit()
            row = connection.execute(
                "select marker from audit_path_probe_20261006"
            ).fetchone()
        finally:
            connection.close()
        print("SQL_READBACK", database_path, row[0] if row else "")
        if row is None or row[0] != MARKER:
            unexpected = True

    print("PATH_PROBE_FAILED" if unexpected else "PATH_PROBE_PASSED")
    return 1 if unexpected else 0


if __name__ == "__main__":
    raise SystemExit(main())
