"""Count one synthetic frontend account. Prints a count, not the record."""

from __future__ import annotations

import json
from pathlib import Path

TARGET = "audit.fe2.20261006@example.com"
body = json.loads(Path("/var/lib/healthcore/auth/auth.json").read_text(encoding="utf-8"))
count = 0
if isinstance(body, dict):
    for table in body.values():
        if not isinstance(table, dict):
            continue
        for row in table.values():
            if isinstance(row, dict) and row.get("email") == TARGET:
                count += 1
print("SYNTHETIC_UI_USER_ROWS", count)
