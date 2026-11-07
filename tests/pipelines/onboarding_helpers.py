"""Shared fictional fixtures for Task 3 onboarding tests."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from agents.onboarding_orchestrator.calendar import CalendarPolicy, FrozenClock
from agents.onboarding_orchestrator.checks import questions_for
from agents.onboarding_orchestrator.runtime import OnboardingRuntime
from agents.onboarding_orchestrator.seed import onboarding_specs
from agents.onboarding_orchestrator.store import OnboardingPaths

USER_IDS = {
    "manager_digital": "mgr-digital",
    "manager_revenue": "mgr-revenue",
    "claire": "user-claire",
    "diane": "user-diane",
    "people_ops": "user-people",
    "hire_austin": "hire-austin",
    "hire_london": "hire-london",
    "hire_early": "hire-early",
}

ACTORS = {
    "people": {"user_id": USER_IDS["people_ops"], "department_id": "people_workforce", "role": "employee"},
    "claire": {"user_id": USER_IDS["claire"], "department_id": "compliance", "role": "supervisor"},
    "diane": {"user_id": USER_IDS["diane"], "department_id": "people_workforce", "role": "supervisor"},
    "manager_digital": {"user_id": USER_IDS["manager_digital"], "department_id": "technology", "role": "supervisor"},
    "manager_revenue": {"user_id": USER_IDS["manager_revenue"], "department_id": "revenue_cycle", "role": "supervisor"},
    "hire_austin": {"user_id": USER_IDS["hire_austin"], "department_id": "technology", "role": "employee"},
    "hire_london": {"user_id": USER_IDS["hire_london"], "department_id": "revenue_cycle", "role": "employee"},
    "hire_early": {"user_id": USER_IDS["hire_early"], "department_id": "technology", "role": "employee"},
    "wrong_manager": {"user_id": USER_IDS["manager_revenue"], "department_id": "revenue_cycle", "role": "supervisor"},
    "admin_other": {"user_id": "admin-tech", "department_id": "technology", "role": "admin"},
}


def make_runtime(tmp_path: Path, now: datetime | None = None) -> OnboardingRuntime:
    paths = OnboardingPaths(
        checkpoint=tmp_path / "checkpoints.sqlite",
        store=tmp_path / "store.json",
        audit=tmp_path / "audit.jsonl",
        outbox=tmp_path / "outbox.jsonl",
    )
    clock = FrozenClock(now or datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc))
    calendar = CalendarPolicy(
        timezone_name="UTC",
        start_date_counts_as_day=1,
        holidays=(),
        cutoff_hour=None,
        reminder_hours_before=24,
    )
    return OnboardingRuntime(paths, clock=clock, calendar=calendar)


def start_three(runtime: OnboardingRuntime, start: date | None = None) -> dict[str, dict]:
    specs = onboarding_specs(USER_IDS, start or date(2026, 11, 9))
    return {spec["onboarding_id"]: runtime.start(spec) for spec in specs}


def complete_paperwork(runtime: OnboardingRuntime, record: dict, people=None) -> dict:
    actor = people or ACTORS["people"]
    return runtime.apply_event(
        record["onboarding_id"],
        {
            "type": "people_receipt",
            "documents_received": True,
            "background_check_completed": True,
            "decision_nonce": record["decision_nonce"],
        },
        actor,
    )


def submit_answers(runtime: OnboardingRuntime, record: dict, actor: dict, *, wrong: bool = False) -> dict:
    stage = int(record["current_stage"])
    bank = record["active_bank"].get(str(stage), "a")
    questions = questions_for(
        stage, framework=record["framework"], role_key=record["role_key"], bank=bank
    )
    answers = [int(item["answer"]) for item in questions]
    if wrong:
        answers = [(answer + 1) % len(questions[0]["choices"]) for answer in answers]
    return runtime.apply_event(
        record["onboarding_id"],
        {"type": "submit_check", "answers": answers, "decision_nonce": record["decision_nonce"]},
        actor,
    )


def decide(runtime: OnboardingRuntime, record: dict, actor: dict, decision: str, comment: str = "") -> dict:
    return runtime.apply_event(
        record["onboarding_id"],
        {
            "type": "human_decision",
            "decision": decision,
            "comment": comment,
            "decision_nonce": record["decision_nonce"],
        },
        actor,
    )
