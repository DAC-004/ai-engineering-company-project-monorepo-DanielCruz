"""Append-only agent action log. Payloads are sanitized before write."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock

from agents.supplier_contracts.identity import actor_payload
from agents.supplier_contracts.privacy import REDACTED, assert_clean_mapping, sanitize_contract_text


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        self._lock = FileLock(str(path) + ".lock")

    def write(self, agent_id: str, tool: str, **fields: Any) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in fields.items():
            if isinstance(value, str):
                cleaned[key] = sanitize_contract_text(value)
            else:
                cleaned[key] = value
        payload = {
            **actor_payload(agent_id),
            "tool": tool,
            "at": datetime.now(timezone.utc).isoformat(),
            **cleaned,
        }
        assert_clean_mapping(payload)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload) + "\n")
        return payload

    def text(self) -> str:
        return self.path.read_text(encoding="utf-8")
