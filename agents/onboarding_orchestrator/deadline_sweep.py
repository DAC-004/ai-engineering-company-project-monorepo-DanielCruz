"""Owned deadline sweep trigger. Frequency is operational config, not HR policy.

The briefing requires a 24-hour reminder and overdue escalation. It does not
set a poll cadence. HTTP tick remains available; autonomous processing must
not depend on it and must not send real communications.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any

SWEEP_INTERVAL_ENV = "ONBOARDING_DEADLINE_SWEEP_INTERVAL_SECONDS"
SWEEP_TASK_NAME = "app.onboarding_tasks.sweep_onboarding_deadlines"


def sweep_interval_seconds(env: Mapping[str, str] | None = None) -> float:
    raw = (env or os.environ).get(SWEEP_INTERVAL_ENV, "").strip()
    if not raw:
        return 0.0
    value = float(raw)
    if value < 0:
        raise ValueError("onboarding_deadline_sweep_interval_invalid")
    return value


def celery_beat_schedule(env: Mapping[str, str] | None = None) -> dict[str, dict[str, Any]]:
    interval = sweep_interval_seconds(env)
    if interval <= 0:
        return {}
    return {
        "onboarding-deadline-sweep": {
            "task": SWEEP_TASK_NAME,
            "schedule": interval,
        }
    }


class OwnedDeadlineScheduler:
    """Bounded background trigger that invokes an owned sweep callable."""

    def __init__(
        self,
        sweep: Callable[[], list[dict[str, Any]]],
        *,
        interval_seconds: float,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._sweep = sweep
        self.interval_seconds = interval_seconds
        self._sleeper = sleeper

    def enabled(self) -> bool:
        return self.interval_seconds > 0

    def run_once(self) -> list[dict[str, Any]]:
        if not self.enabled():
            return []
        return list(self._sweep())

    def run_cycles(self, cycles: int) -> list[dict[str, Any]]:
        emitted: list[dict[str, Any]] = []
        if not self.enabled() or cycles <= 0:
            return emitted
        for index in range(cycles):
            emitted.extend(self.run_once())
            if self._sleeper is not None and index < cycles - 1:
                self._sleeper(self.interval_seconds)
        return emitted
