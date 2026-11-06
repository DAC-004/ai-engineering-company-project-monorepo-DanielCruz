"""JSON projection with process/thread locks. Decimal metadata stays here, not in TinyDB."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from filelock import FileLock

from agents.supplier_contracts.privacy import assert_clean_mapping

T = TypeVar("T")


def empty_document() -> dict[str, Any]:
    return {
        "alerts": [],
        "drafts": {},
        "dpa_proceed": {},
        "calendars": {},
        "outbox": [],
    }


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.RLock()
        self._file = FileLock(str(path) + ".lock")
        with self._thread:
            with self._file:
                if not path.exists():
                    path.write_text(json.dumps(empty_document()), encoding="utf-8")

    def _update(self, mutate: Callable[[dict[str, Any]], T]) -> T:
        with self._thread:
            with self._file:
                document = json.loads(self.path.read_text(encoding="utf-8"))
                result = mutate(document)
                assert_clean_mapping(document)
                self.path.write_text(json.dumps(document, indent=2), encoding="utf-8")
                return result

    def read(self) -> dict[str, Any]:
        with self._thread:
            with self._file:
                return json.loads(self.path.read_text(encoding="utf-8"))

    def append_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        def mutate(document: dict[str, Any]) -> dict[str, Any]:
            document.setdefault("alerts", []).append(alert)
            return alert

        return self._update(mutate)

    def append_alert_if_absent(self, alert: dict[str, Any]) -> dict[str, Any]:
        """Check and insert under one FileLock so concurrent processes cannot duplicate."""

        def mutate(document: dict[str, Any]) -> dict[str, Any]:
            key = alert["idempotency_key"]
            existing = document.setdefault("alerts", [])
            if any(item.get("idempotency_key") == key for item in existing):
                return {}
            existing.append(alert)
            return alert

        return self._update(mutate)

    def save_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        def mutate(document: dict[str, Any]) -> dict[str, Any]:
            document.setdefault("drafts", {})[draft["draft_id"]] = draft
            return draft

        return self._update(mutate)

    def cas_update_draft(
        self,
        draft_id: str,
        *,
        expected_nonce: str,
        expected_version: int,
        expected_hash: str,
        updater: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Reject stale version/hash, replayed nonce, and concurrent terminal state under one lock."""

        def mutate(document: dict[str, Any]) -> dict[str, Any]:
            current = document.get("drafts", {}).get(draft_id)
            if current is None:
                raise KeyError("unknown_draft")
            if current.get("state") != "pending":
                raise ValueError("concurrent_terminal_state")
            if int(current.get("version", -1)) != expected_version:
                raise ValueError("stale_draft_version")
            if current.get("content_sha256") != expected_hash:
                raise ValueError("stale_draft_hash")
            if current.get("approval_nonce") != expected_nonce:
                raise ValueError("stale_or_replayed_nonce")
            updated = updater(dict(current))
            document["drafts"][draft_id] = updated
            return updated

        return self._update(mutate)

    def set_dpa_proceed(self, supplier_id: str, confirmed: bool) -> None:
        def mutate(document: dict[str, Any]) -> None:
            document.setdefault("dpa_proceed", {})[supplier_id] = confirmed

        self._update(mutate)

    def dpa_proceed(self, supplier_id: str) -> bool:
        return bool(self.read().get("dpa_proceed", {}).get(supplier_id))

    def save_calendar(self, supplier_id: str, payload: dict[str, str]) -> None:
        def mutate(document: dict[str, Any]) -> None:
            document.setdefault("calendars", {})[supplier_id] = payload

        self._update(mutate)
