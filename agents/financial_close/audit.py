"""Append-only automated-process audit. Never write raw source text."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agents.financial_close.constants import AGENT_ID
from agents.financial_close.privacy import assert_clean_mapping


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")

    def record(self, action: str, **fields: object) -> None:
        payload = {
            "at": datetime.now(timezone.utc).isoformat(),
            "actor_type": "automated_process",
            "actor_id": AGENT_ID,
            "action": action,
            **fields,
        }
        assert_clean_mapping(payload)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
