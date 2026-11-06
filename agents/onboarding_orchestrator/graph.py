"""Explicit seven-stage LangGraph. Human gates are interrupts, not timeouts."""

from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from agents.onboarding_orchestrator.checks import score_answers
from agents.onboarding_orchestrator.identity import AGENT_ACTOR_ID, AGENT_ACTOR_TYPE
from agents.onboarding_orchestrator.sensitive import scan_mapping
from agents.onboarding_orchestrator.state import OnboardingState

PendingKind = Literal["paperwork", "check", "compliance_approval", "manager_approval", "closure"]


def _nonce() -> str:
    return uuid4().hex


def _attempts(state: OnboardingState, stage: int) -> int:
    return int(state["attempt_counts"].get(str(stage), 0))


def _set_attempt(state: OnboardingState, stage: int, value: int) -> dict[str, int]:
    updated = dict(state["attempt_counts"])
    updated[str(stage)] = value
    return updated


def _set_bank(state: OnboardingState, stage: int, bank: str) -> dict[str, str]:
    updated = dict(state["active_bank"])
    updated[str(stage)] = bank
    return updated


def _interrupt(kind: PendingKind, stage: int, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "kind": kind,
        "stage": stage,
        "actor_type": AGENT_ACTOR_TYPE,
        "actor_id": AGENT_ACTOR_ID,
    }
    if extra:
        payload.update(extra)
    resumed = interrupt(payload)
    if not isinstance(resumed, dict):
        raise ValueError("invalid_resume_payload")
    scan_mapping(resumed)
    return resumed


def paperwork_gate(state: OnboardingState) -> dict[str, Any]:
    event = _interrupt("paperwork", 1)
    received = bool(event.get("documents_received"))
    completed = bool(event.get("background_check_completed"))
    if not received or not completed:
        return {
            "paperwork_received": received,
            "background_check_completed": completed,
            "current_stage": 1,
            "status": "waiting_human",
            "pending_kind": "paperwork",
            "decision_nonce": _nonce(),
            "last_action": "paperwork_incomplete",
        }
    return {
        "paperwork_received": True,
        "background_check_completed": True,
        "current_stage": 2,
        "status": "waiting_check",
        "pending_kind": "check",
        "decision_nonce": _nonce(),
        "last_action": "paperwork_accepted",
        "last_rejection_comment": "",
    }


def _run_content_check(state: OnboardingState, stage: int) -> dict[str, Any]:
    bank = state["active_bank"].get(str(stage), "a")
    event = _interrupt("check", stage, {"bank": bank})
    answers = event.get("answers")
    if not isinstance(answers, list):
        raise ValueError("answers_required")
    result = score_answers(
        stage,
        [int(item) for item in answers],
        framework=state["framework"],
        role_key=state["role_key"],
        bank=bank,
        prior_attempts=_attempts(state, stage),
    )
    update: dict[str, Any] = {
        "last_score": result.score,
        "missed_topics": list(result.missed_topics),
        "attempt_counts": _set_attempt(state, stage, result.attempt),
        "active_bank": _set_bank(state, stage, result.next_bank),
        "decision_nonce": _nonce(),
        "last_action": "check_passed" if result.passed else "check_failed",
        "last_rejection_comment": "",
    }
    if result.notify:
        update["last_action"] = f"check_failed_notify_{result.notify}"
    if not result.passed:
        update.update(
            {
                "status": "waiting_check",
                "pending_kind": "check",
                "current_stage": stage,
            }
        )
        return update
    if stage == 2:
        update.update(
            {
                "company_passed": True,
                "current_stage": 3,
                "status": "waiting_check",
                "pending_kind": "check",
            }
        )
    elif stage == 3:
        update.update(
            {
                "operations_passed": True,
                "current_stage": 4,
                "status": "waiting_check",
                "pending_kind": "check",
            }
        )
    elif stage == 4:
        update.update(
            {
                "compliance_check_passed": True,
                "current_stage": 4,
                "status": "waiting_human",
                "pending_kind": "compliance_approval",
            }
        )
    elif stage == 5:
        update.update(
            {
                "role_check_passed": True,
                "current_stage": 5,
                "status": "waiting_human",
                "pending_kind": "manager_approval",
            }
        )
    elif stage == 6:
        update.update(
            {
                "how_we_work_passed": True,
                "current_stage": 7,
                "status": "waiting_human",
                "pending_kind": "closure",
            }
        )
    return update


def company_check(state: OnboardingState) -> dict[str, Any]:
    return _run_content_check(state, 2)


def operations_check(state: OnboardingState) -> dict[str, Any]:
    return _run_content_check(state, 3)


def compliance_check(state: OnboardingState) -> dict[str, Any]:
    return _run_content_check(state, 4)


def role_check(state: OnboardingState) -> dict[str, Any]:
    return _run_content_check(state, 5)


def how_we_work_check(state: OnboardingState) -> dict[str, Any]:
    return _run_content_check(state, 6)


def _apply_approval(
    state: OnboardingState,
    *,
    kind: PendingKind,
    stage: int,
    approve_fields: dict[str, Any],
    reject_fields: dict[str, Any],
) -> dict[str, Any]:
    event = _interrupt(kind, stage)
    decision = str(event.get("decision") or "")
    comment = str(event.get("comment") or "")
    if decision == "approve":
        update = {
            **approve_fields,
            "last_rejection_comment": "",
            "decision_nonce": _nonce(),
            "last_action": f"stage_{stage}_approved",
        }
        return update
    if decision == "reject":
        return {
            **reject_fields,
            "last_rejection_comment": comment,
            "decision_nonce": _nonce(),
            "last_action": f"stage_{stage}_rejected",
            "status": "waiting_check" if stage in {4, 5} else "waiting_human",
        }
    raise ValueError("decision_required")


def compliance_approval(state: OnboardingState) -> dict[str, Any]:
    return _apply_approval(
        state,
        kind="compliance_approval",
        stage=4,
        approve_fields={
            "compliance_approved": True,
            "current_stage": 5,
            "status": "waiting_check",
            "pending_kind": "check",
        },
        reject_fields={
            "compliance_approved": False,
            "compliance_check_passed": False,
            "current_stage": 4,
            "pending_kind": "check",
            "active_bank": _set_bank(state, 4, "a"),
        },
    )


def role_approval(state: OnboardingState) -> dict[str, Any]:
    return _apply_approval(
        state,
        kind="manager_approval",
        stage=5,
        approve_fields={
            "role_approved": True,
            "current_stage": 6,
            "status": "waiting_check",
            "pending_kind": "check",
        },
        reject_fields={
            "role_approved": False,
            "role_check_passed": False,
            "current_stage": 5,
            "pending_kind": "check",
            "active_bank": _set_bank(state, 5, "a"),
        },
    )


def closure_approval(state: OnboardingState) -> dict[str, Any]:
    return _apply_approval(
        state,
        kind="closure",
        stage=7,
        approve_fields={
            "closure_approved": True,
            "current_stage": 7,
            "status": "complete",
            "pending_kind": "",
        },
        reject_fields={
            "closure_approved": False,
            "current_stage": 7,
            "pending_kind": "closure",
            "status": "waiting_human",
        },
    )


def mark_complete(state: OnboardingState) -> dict[str, Any]:
    return {"status": "complete", "pending_kind": "", "last_action": "onboarding_complete"}


def _route_paperwork(state: OnboardingState) -> str:
    if state["paperwork_received"] and state["background_check_completed"]:
        return "company"
    return "wait"


def _route_check(stage: int, pass_key: str, on_pass: str):
    def route(state: OnboardingState) -> str:
        if state[pass_key]:  # type: ignore[literal-required]
            return on_pass
        return "retry"

    route.__name__ = f"route_stage_{stage}"
    return route


def _route_compliance_approval(state: OnboardingState) -> str:
    if state["compliance_approved"]:
        return "next"
    return "restart"


def _route_role_approval(state: OnboardingState) -> str:
    if state["role_approved"]:
        return "next"
    return "restart"


def _route_closure(state: OnboardingState) -> str:
    if state["closure_approved"]:
        return "done"
    return "wait"


def build_onboarding_graph() -> StateGraph[OnboardingState]:
    builder: StateGraph[OnboardingState] = StateGraph(OnboardingState)
    builder.add_node("paperwork_gate", paperwork_gate)
    builder.add_node("company_check", company_check)
    builder.add_node("operations_check", operations_check)
    builder.add_node("compliance_check", compliance_check)
    builder.add_node("compliance_approval", compliance_approval)
    builder.add_node("role_check", role_check)
    builder.add_node("role_approval", role_approval)
    builder.add_node("how_we_work_check", how_we_work_check)
    builder.add_node("closure_approval", closure_approval)
    builder.add_node("mark_complete", mark_complete)
    builder.add_edge(START, "paperwork_gate")
    builder.add_conditional_edges(
        "paperwork_gate",
        _route_paperwork,
        {"company": "company_check", "wait": "paperwork_gate"},
    )
    builder.add_conditional_edges(
        "company_check",
        _route_check(2, "company_passed", "next"),
        {"next": "operations_check", "retry": "company_check"},
    )
    builder.add_conditional_edges(
        "operations_check",
        _route_check(3, "operations_passed", "next"),
        {"next": "compliance_check", "retry": "operations_check"},
    )
    builder.add_conditional_edges(
        "compliance_check",
        _route_check(4, "compliance_check_passed", "next"),
        {"next": "compliance_approval", "retry": "compliance_check"},
    )
    builder.add_conditional_edges(
        "compliance_approval",
        _route_compliance_approval,
        {"next": "role_check", "restart": "compliance_check"},
    )
    builder.add_conditional_edges(
        "role_check",
        _route_check(5, "role_check_passed", "next"),
        {"next": "role_approval", "retry": "role_check"},
    )
    builder.add_conditional_edges(
        "role_approval",
        _route_role_approval,
        {"next": "how_we_work_check", "restart": "role_check"},
    )
    builder.add_conditional_edges(
        "how_we_work_check",
        _route_check(6, "how_we_work_passed", "next"),
        {"next": "closure_approval", "retry": "how_we_work_check"},
    )
    builder.add_conditional_edges(
        "closure_approval",
        _route_closure,
        {"done": "mark_complete", "wait": "closure_approval"},
    )
    builder.add_edge("mark_complete", END)
    return builder


def compile_onboarding_graph(checkpointer: SqliteSaver) -> CompiledStateGraph:
    return build_onboarding_graph().compile(checkpointer=checkpointer)
