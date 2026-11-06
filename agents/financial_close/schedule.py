"""Third business day 06:00 America/Chicago, weekday default, configurable holidays."""

from __future__ import annotations

from agents.financial_close.agent import run_close
from agents.financial_close.store import PeriodRunBusy
from agents.financial_close.calendar import austin_now, closing_period_for_load_date, due_instant_for_period
from agents.financial_close.runtime import CloseRuntime, runtime as default_runtime
from agents.financial_close.tools import build_facts


def due_period(runtime: CloseRuntime) -> str:
    load = runtime.load_date()
    return closing_period_for_load_date(load)


def should_run(runtime: CloseRuntime) -> tuple[bool, bool, str]:
    """Return (run, catch_up, period). Source identity changes invalidate a cached close."""
    now = austin_now(runtime.clock, runtime.policy)
    period = due_period(runtime)
    due = due_instant_for_period(period, runtime.policy)
    facts = build_facts(raw_dir=runtime.raw, load_date=runtime.load_date(), catch_up=False)
    existing = runtime.store.get_close(period)
    if (
        existing
        and existing["facts_digest"] == facts.digest
        and existing["status"] in {"awaiting_tom", "approved"}
    ):
        return False, False, period
    if now >= due:
        later_day = now.date() > due.date()
        return True, later_day, period
    return False, False, period


def tick(runtime: CloseRuntime | None = None) -> dict:
    current = runtime or default_runtime()
    run, catch_up, period = should_run(current)
    if not run:
        current.audit.record("schedule_skip", period=period)
        return {"ran": False, "period": period, "catch_up": catch_up}
    try:
        draft = run_close(current, catch_up=catch_up)
    except PeriodRunBusy as exc:
        current.audit.record("schedule_busy", period=period)
        return {"ran": False, "period": period, "catch_up": catch_up, "draft_id": exc.draft_id, "reason": "busy"}
    current.audit.record("schedule_run", period=period, draft_id=draft["draft_id"], catch_up=catch_up)
    return {"ran": True, "period": period, "catch_up": catch_up, "draft_id": draft["draft_id"]}
