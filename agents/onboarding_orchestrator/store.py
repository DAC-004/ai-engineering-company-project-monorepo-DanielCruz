"""JSON projection, audit, and internal outbox. Checkpointer remains source for resume.

Read-modify-write of the projection file is covered by a process FileLock and a
thread RLock so two workers cannot drop each other's onboardings.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4

from filelock import FileLock

from agents.onboarding_orchestrator.identity import actor_payload
from agents.onboarding_orchestrator.sensitive import redact_text, scan_mapping

_LOCK = threading.RLock()
T = TypeVar("T")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class OnboardingPaths:
    checkpoint: Path
    store: Path
    audit: Path
    outbox: Path


def empty_document() -> dict[str, Any]:
    return {"onboardings": {}, "access_requests": [], "notices": []}


class JsonStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file_lock = FileLock(str(path) + ".lock")
        with _LOCK:
            with self._file_lock:
                if not path.exists():
                    path.write_text(json.dumps(empty_document()), encoding="utf-8")

    def _update(self, mutate: Callable[[dict[str, Any]], T]) -> T:
        """Hold thread and file locks across read, mutate, and write."""
        with _LOCK:
            with self._file_lock:
                document = json.loads(self.path.read_text(encoding="utf-8"))
                result = mutate(document)
                self.path.write_text(json.dumps(document, indent=2), encoding="utf-8")
                return result

    def read(self) -> dict[str, Any]:
        with _LOCK:
            with self._file_lock:
                return json.loads(self.path.read_text(encoding="utf-8"))

    def write(self, document: dict[str, Any]) -> None:
        with _LOCK:
            with self._file_lock:
                self.path.write_text(json.dumps(document, indent=2), encoding="utf-8")

    def upsert_onboarding(self, record: dict[str, Any]) -> dict[str, Any]:
        scan_mapping(record)

        def mutate(document: dict[str, Any]) -> dict[str, Any]:
            document.setdefault("onboardings", {})[record["onboarding_id"]] = record
            return record

        return self._update(mutate)

    def get(self, onboarding_id: str) -> dict[str, Any] | None:
        return self.read()["onboardings"].get(onboarding_id)

    def list_all(self) -> list[dict[str, Any]]:
        return list(self.read()["onboardings"].values())

    def append_access(self, row: dict[str, Any]) -> dict[str, Any]:
        scan_mapping(row)

        def mutate(document: dict[str, Any]) -> dict[str, Any]:
            document.setdefault("access_requests", []).append(row)
            return row

        return self._update(mutate)

    def append_notice(self, row: dict[str, Any]) -> dict[str, Any]:
        scan_mapping(row)

        def mutate(document: dict[str, Any]) -> dict[str, Any]:
            document.setdefault("notices", []).append(row)
            return row

        return self._update(mutate)


class InternalOutbox:
    """Append-only in-app outbox. External mail/HTTP transports are not authorized."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        self._file_lock = FileLock(str(path) + ".lock")

    def append(self, notice: dict[str, Any]) -> dict[str, Any]:
        if notice.get("channel") != "internal_outbox":
            raise ValueError("real_communications_not_authorized")
        scan_mapping(notice)
        with _LOCK:
            with self._file_lock:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(notice) + "\n")
        return notice

    def lines(self) -> list[dict[str, Any]]:
        text = self.path.read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        self._file_lock = FileLock(str(path) + ".lock")

    def write(self, action: str, **fields: Any) -> dict[str, Any]:
        payload = {
            **actor_payload(),
            "action": action,
            "at": _now(),
        }
        for key, value in fields.items():
            if isinstance(value, str):
                payload[key] = redact_text(value)
            else:
                payload[key] = value
        scan_mapping({k: v for k, v in payload.items() if k not in {"at", "actor_type", "actor_id"}})
        with _LOCK:
            with self._file_lock:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload) + "\n")
        return payload

    def lines(self) -> list[dict[str, Any]]:
        text = self.path.read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def new_notice(
    *,
    kind: str,
    recipient: str,
    onboarding_id: str,
    template: str,
    stage: int,
) -> dict[str, Any]:
    return {
        "id": uuid4().hex,
        "kind": kind,
        "recipient": recipient,
        "onboarding_id": onboarding_id,
        "template": template,
        "stage": stage,
        "channel": "internal_outbox",
        "at": _now(),
    }
