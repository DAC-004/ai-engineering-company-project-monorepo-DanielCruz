"""Owned process paths, fixtures, and stores for the financial close."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from agents.financial_close.audit import AuditLog
from agents.financial_close.calendar import CalendarPolicy, SystemClock, policy_from_env
from agents.financial_close.generation import configured_transport
from agents.financial_close.store import CloseStore

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = REPO_ROOT / "data" / "raw" / "healthcore-financial-close"
DEFAULT_PROCESS = REPO_ROOT / "data" / "process" / "financial-close"
DEFAULT_LOAD_DATE = date(2026, 11, 6)


def _path_from_env(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip()
    return Path(raw) if raw else default


def raw_dir() -> Path:
    return _path_from_env("FINANCIAL_CLOSE_RAW_DIR", DEFAULT_RAW)


def process_dir() -> Path:
    return _path_from_env("FINANCIAL_CLOSE_PROCESS_DIR", DEFAULT_PROCESS)


def load_date_from_env() -> date | None:
    raw = os.environ.get("FINANCIAL_CLOSE_LOAD_DATE", "").strip()
    return date.fromisoformat(raw) if raw else None


class CloseRuntime:
    def __init__(
        self,
        *,
        raw: Path | None = None,
        process: Path | None = None,
        as_of: date | None = None,
        clock=None,
        policy: CalendarPolicy | None = None,
        transport=configured_transport,
    ) -> None:
        self.raw = raw or raw_dir()
        self.process = process or process_dir()
        self.process.mkdir(parents=True, exist_ok=True)
        self.clock = clock or SystemClock()
        self.policy = policy or policy_from_env()
        self.transport = transport
        env_load = load_date_from_env()
        self.configured_load_date = as_of or env_load
        self.store = CloseStore(self.process / "close.sqlite")
        self.audit = AuditLog(self.process / "audit.jsonl")

    def load_date(self) -> date:
        if self.configured_load_date is not None:
            return self.configured_load_date
        from agents.financial_close.calendar import austin_now

        return austin_now(self.clock, self.policy).date()


_RUNTIME: CloseRuntime | None = None


def runtime() -> CloseRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = CloseRuntime()
    return _RUNTIME


def reset_runtime_for_tests(instance: CloseRuntime | None = None) -> CloseRuntime | None:
    global _RUNTIME
    _RUNTIME = instance
    return _RUNTIME
