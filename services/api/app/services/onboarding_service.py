"""API adapter around the onboarding runtime. Uses owned disposable paths."""

from __future__ import annotations

import os
from pathlib import Path

from agents.onboarding_orchestrator.calendar import CalendarPolicy, FrozenClock
from agents.onboarding_orchestrator.runtime import OnboardingError, OnboardingRuntime, default_paths
from agents.onboarding_orchestrator.store import OnboardingPaths
from shared.healthcore_rag.config import REPO_ROOT

_runtime: OnboardingRuntime | None = None


def reset_onboarding_runtime() -> None:
    global _runtime
    _runtime = None


def _paths_from_env() -> OnboardingPaths:
    checkpoint = os.environ.get("ONBOARDING_CHECKPOINT_PATH")
    store = os.environ.get("ONBOARDING_STORE_PATH")
    audit = os.environ.get("ONBOARDING_AUDIT_PATH")
    if checkpoint and store and audit:
        return OnboardingPaths(
            checkpoint=Path(checkpoint),
            store=Path(store),
            audit=Path(audit),
            outbox=Path(os.environ.get("ONBOARDING_OUTBOX_PATH") or Path(store).with_name("outbox.jsonl")),
        )
    return default_paths(REPO_ROOT)


def _calendar_from_env() -> CalendarPolicy:
    start_as = int(os.environ.get("ONBOARDING_START_DATE_COUNTS_AS_DAY", "1"))
    holidays = tuple(
        item for item in os.environ.get("ONBOARDING_HOLIDAYS", "").split(",") if item.strip()
    )
    cutoff_raw = os.environ.get("ONBOARDING_CUTOFF_HOUR", "").strip()
    cutoff = int(cutoff_raw) if cutoff_raw else None
    return CalendarPolicy(
        timezone_name=os.environ.get("ONBOARDING_TIMEZONE", "UTC"),
        start_date_counts_as_day=start_as,
        holidays=holidays,
        cutoff_hour=cutoff,
    )


def get_runtime() -> OnboardingRuntime:
    global _runtime
    if _runtime is None:
        clock = None
        frozen = os.environ.get("ONBOARDING_FROZEN_NOW", "").strip()
        if frozen:
            from datetime import datetime

            clock = FrozenClock(datetime.fromisoformat(frozen))
        _runtime = OnboardingRuntime(_paths_from_env(), clock=clock, calendar=_calendar_from_env())
    return _runtime


def actor_from_user(user) -> dict[str, str]:
    return {"user_id": user.id, "department_id": user.department_id or "", "role": user.role.value}
