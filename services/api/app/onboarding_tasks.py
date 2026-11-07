"""Background worker entry for onboarding graph events."""

from __future__ import annotations
from app.audit.process import audited_process

from typing import Any

from app.celery_app import celery_app
from app.services.onboarding_service import get_runtime
from agents.onboarding_orchestrator.identity import AGENT_ACTOR_ID, AGENT_ACTOR_TYPE


@celery_app.task(name="app.onboarding_tasks.start_onboarding")
@audited_process("process:onboarding", "people_workforce")
def start_onboarding_task(spec: dict[str, Any]) -> dict[str, Any]:
    record = get_runtime().start(spec)
    return {
        "actor_type": AGENT_ACTOR_TYPE,
        "actor_id": AGENT_ACTOR_ID,
        **record,
    }


@celery_app.task(name="app.onboarding_tasks.run_onboarding_event")
@audited_process("process:onboarding", "people_workforce")
def run_onboarding_event(onboarding_id: str, event: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    record = get_runtime().apply_event(onboarding_id, event, actor)
    return {
        "actor_type": AGENT_ACTOR_TYPE,
        "actor_id": AGENT_ACTOR_ID,
        **record,
    }


@celery_app.task(name="app.onboarding_tasks.tick_onboarding_deadlines")
@audited_process("process:onboarding", "people_workforce")
def tick_onboarding_deadlines(onboarding_id: str) -> dict[str, Any]:
    notices = get_runtime().process_deadlines(onboarding_id)
    return {
        "actor_type": AGENT_ACTOR_TYPE,
        "actor_id": AGENT_ACTOR_ID,
        "onboarding_id": onboarding_id,
        "notice_count": len(notices),
        "channel": "internal_outbox",
    }


@celery_app.task(name="app.onboarding_tasks.sweep_onboarding_deadlines")
@audited_process("process:onboarding", "people_workforce")
def sweep_onboarding_deadlines() -> dict[str, Any]:
    """Autonomous sweep. Interval is operational config; no HTTP or real communications."""
    notices = get_runtime().process_all_deadlines()
    return {
        "actor_type": AGENT_ACTOR_TYPE,
        "actor_id": AGENT_ACTOR_ID,
        "notice_count": len(notices),
        "channel": "internal_outbox",
    }
