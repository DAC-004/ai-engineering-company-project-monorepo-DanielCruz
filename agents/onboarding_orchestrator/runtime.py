"""Durable run/resume for one onboarding thread. Background callers invoke this."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4

from filelock import FileLock
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from agents.onboarding_orchestrator.access import evaluate_access_request
from agents.onboarding_orchestrator.calendar import CalendarPolicy, Clock, SystemClock, evaluate_stage_timing
from agents.onboarding_orchestrator.checks import questions_for
from agents.onboarding_orchestrator.content import presented_content
from agents.onboarding_orchestrator.graph import compile_onboarding_graph
from agents.onboarding_orchestrator.qa import answer_question
from agents.onboarding_orchestrator.sensitive import SensitiveDataError, scan_mapping
from agents.onboarding_orchestrator.state import (
    CONTENT_STAGES,
    FRAMEWORK_HIPAA,
    FRAMEWORK_UK_GDPR,
    ROLE_DIGITAL_ENGINEER,
    ROLE_REVENUE_ANALYST,
    STAGE_NAMES,
    initial_state,
)
from agents.onboarding_orchestrator.store import AuditLog, InternalOutbox, JsonStore, OnboardingPaths, new_notice

T = TypeVar("T")

KIND_TO_EVENT = {
    "paperwork": "people_receipt",
    "check": "submit_check",
    "compliance_approval": "human_decision",
    "manager_approval": "human_decision",
    "closure": "human_decision",
}


class OnboardingError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_ALLOWED_OFFICES = {"Austin": FRAMEWORK_HIPAA, "London": FRAMEWORK_UK_GDPR}
_ALLOWED_DEPARTMENTS = frozenset(
    {
        "technology",
        "revenue_cycle",
        "compliance",
        "people_workforce",
        "patient_experience",
    }
)
_APPROVER_ROLES = frozenset({"supervisor", "admin"})


def validate_start_spec(spec: dict[str, Any]) -> None:
    office = str(spec.get("office") or "")
    framework = str(spec.get("framework") or "")
    role_key = str(spec.get("role_key") or "")
    department_id = str(spec.get("department_id") or "")
    if office not in _ALLOWED_OFFICES:
        raise OnboardingError("invalid_office")
    if framework not in {FRAMEWORK_HIPAA, FRAMEWORK_UK_GDPR}:
        raise OnboardingError("invalid_framework")
    if _ALLOWED_OFFICES[office] != framework:
        raise OnboardingError("framework_office_mismatch")
    if role_key not in {ROLE_DIGITAL_ENGINEER, ROLE_REVENUE_ANALYST}:
        raise OnboardingError("invalid_role_key")
    if department_id not in _ALLOWED_DEPARTMENTS:
        raise OnboardingError("invalid_department")


def with_checkpointer(path: Path, use: Callable[[SqliteSaver], T]) -> T:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".lock")
    with lock:
        connection = sqlite3.connect(str(path), check_same_thread=False)
        try:
            saver = SqliteSaver(connection)
            saver.setup()
            return use(saver)
        finally:
            connection.close()


def thread_id(onboarding_id: str) -> str:
    return f"onboarding-{onboarding_id}"


def _config(onboarding_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id(onboarding_id)}}


class OnboardingRuntime:
    def __init__(
        self,
        paths: OnboardingPaths,
        *,
        clock: Clock | None = None,
        calendar: CalendarPolicy | None = None,
    ) -> None:
        self.paths = paths
        self.store = JsonStore(paths.store)
        self.audit = AuditLog(paths.audit)
        self.outbox = InternalOutbox(paths.outbox)
        self.clock = clock or SystemClock()
        self.calendar = calendar or CalendarPolicy()

    def _snapshot(self, compiled, onboarding_id: str):
        return compiled.get_state(_config(onboarding_id))

    def _project(self, values: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
        record = {
            "onboarding_id": values["onboarding_id"],
            "hire_user_id": values["hire_user_id"],
            "display_name": values["display_name"],
            "role_key": values["role_key"],
            "department_id": values["department_id"],
            "office": values["office"],
            "framework": values["framework"],
            "manager_user_id": values["manager_user_id"],
            "claire_user_id": values["claire_user_id"],
            "diane_user_id": values["diane_user_id"],
            "people_team_department_id": values["people_team_department_id"],
            "start_date": values["start_date"],
            "current_stage": values["current_stage"],
            "stage_name": STAGE_NAMES[int(values["current_stage"])],
            "status": values["status"],
            "pending_kind": values["pending_kind"],
            "decision_nonce": values["decision_nonce"],
            "paperwork_received": values["paperwork_received"],
            "background_check_completed": values["background_check_completed"],
            "company_passed": values["company_passed"],
            "operations_passed": values["operations_passed"],
            "compliance_check_passed": values["compliance_check_passed"],
            "compliance_approved": values["compliance_approved"],
            "role_check_passed": values["role_check_passed"],
            "role_approved": values["role_approved"],
            "how_we_work_passed": values["how_we_work_passed"],
            "closure_approved": values["closure_approved"],
            "attempt_counts": values["attempt_counts"],
            "active_bank": values["active_bank"],
            "missed_topics": values["missed_topics"],
            "last_score": values["last_score"],
            "last_rejection_comment": values["last_rejection_comment"],
            "last_action": values["last_action"],
            "blocked": values["pending_kind"] in {"paperwork", "compliance_approval", "manager_approval", "closure"}
            or values["status"] == "waiting_human",
            "reminders_sent": extra.get("reminders_sent") if extra else None,
            "escalations_sent": extra.get("escalations_sent") if extra else None,
        }
        existing = self.store.get(values["onboarding_id"]) or {}
        if record["reminders_sent"] is None:
            record["reminders_sent"] = existing.get("reminders_sent") or {}
        if record["escalations_sent"] is None:
            record["escalations_sent"] = existing.get("escalations_sent") or {}
        self.store.upsert_onboarding(record)
        return record

    def start(self, spec: dict[str, Any]) -> dict[str, Any]:
        scan_mapping(spec)
        validate_start_spec(spec)
        spec = {**spec, "onboarding_id": spec.get("onboarding_id") or uuid4().hex, "decision_nonce": uuid4().hex}
        existing = self.store.get(spec["onboarding_id"])
        if existing and existing.get("status") not in {None, "queued"}:
            return existing

        def run(saver: SqliteSaver) -> dict[str, Any]:
            compiled = compile_onboarding_graph(saver)
            snapshot = self._snapshot(compiled, spec["onboarding_id"])
            if snapshot.values and snapshot.values.get("onboarding_id"):
                return self._project(dict(snapshot.values))
            compiled.invoke(initial_state(spec), _config(spec["onboarding_id"]))
            snapshot = self._snapshot(compiled, spec["onboarding_id"])
            values = dict(snapshot.values)
            if not values.get("decision_nonce"):
                values["decision_nonce"] = spec["decision_nonce"]
            record = self._project(values)
            self.audit.write(
                "onboarding_started",
                onboarding_id=record["onboarding_id"],
                stage=record["current_stage"],
            )
            return record

        return with_checkpointer(self.paths.checkpoint, run)

    def _authorized_decision(self, record: dict[str, Any], actor: dict[str, Any], kind: str) -> None:
        actor_id = str(actor.get("user_id") or "")
        department_id = actor.get("department_id")
        role = str(actor.get("role") or "")
        if kind == "paperwork":
            if department_id != record["people_team_department_id"]:
                raise OnboardingError("unauthorized_approver")
            return
        if kind == "compliance_approval":
            if (
                actor_id != record["claire_user_id"]
                or department_id != "compliance"
                or role not in _APPROVER_ROLES
            ):
                raise OnboardingError("unauthorized_approver")
            return
        if kind == "manager_approval":
            if (
                actor_id != record["manager_user_id"]
                or department_id != record["department_id"]
                or role not in _APPROVER_ROLES
            ):
                raise OnboardingError("unauthorized_approver")
            return
        if kind == "closure":
            if (
                actor_id != record["diane_user_id"]
                or department_id != record["people_team_department_id"]
                or role not in _APPROVER_ROLES
            ):
                raise OnboardingError("unauthorized_approver")
            return
        if kind == "check":
            if actor_id != record["hire_user_id"]:
                raise OnboardingError("unauthorized_actor")
            return
        raise OnboardingError("unknown_pending_kind")

    def assert_event_allowed(
        self, onboarding_id: str, event: dict[str, Any], actor: dict[str, Any]
    ) -> dict[str, Any]:
        scan_mapping(event)
        scan_mapping(actor)
        record = self.store.get(onboarding_id)
        if record is None:
            raise OnboardingError("unknown_onboarding")
        pending = record["pending_kind"]
        expected = KIND_TO_EVENT.get(pending)
        if event.get("type") != expected:
            raise OnboardingError("unexpected_event")
        if event.get("decision_nonce") != record["decision_nonce"]:
            raise OnboardingError("stale_or_duplicate_decision")
        self._authorized_decision(record, actor, pending)
        return record

    def apply_event(self, onboarding_id: str, event: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
        self.assert_event_allowed(onboarding_id, event, actor)

        def run(saver: SqliteSaver) -> dict[str, Any]:
            compiled = compile_onboarding_graph(saver)
            snapshot = self._snapshot(compiled, onboarding_id)
            if not snapshot.next:
                raise OnboardingError("not_interrupted")
            compiled.invoke(Command(resume=event), _config(onboarding_id))
            latest = dict(self._snapshot(compiled, onboarding_id).values)
            projected = self._project(latest)
            action = str(latest.get("last_action") or "resumed")
            self.audit.write(action, onboarding_id=onboarding_id, stage=projected["current_stage"])
            if action.endswith("_notify_claire"):
                self._notice("check_failure", "claire", onboarding_id, projected["current_stage"], "two_failed_compliance_attempts")
            elif action.endswith("_notify_manager"):
                self._notice("check_failure", "manager", onboarding_id, projected["current_stage"], "two_failed_stage_attempts")
            return projected

        return with_checkpointer(self.paths.checkpoint, run)

    def _notice(self, kind: str, recipient: str, onboarding_id: str, stage: int, template: str) -> dict[str, Any]:
        notice = new_notice(
            kind=kind,
            recipient=recipient,
            onboarding_id=onboarding_id,
            template=template,
            stage=stage,
        )
        self.store.append_notice(notice)
        self.outbox.append(notice)
        self.audit.write(
            "internal_notice_enqueued",
            onboarding_id=onboarding_id,
            stage=stage,
            template=template,
            recipient=recipient,
            channel="internal_outbox",
        )
        return notice

    def current(self, onboarding_id: str) -> dict[str, Any]:
        record = self.store.get(onboarding_id)
        if record is None:
            raise OnboardingError("unknown_onboarding")
        return record

    def checkpoint_values(self, onboarding_id: str) -> dict[str, Any]:
        def run(saver: SqliteSaver) -> dict[str, Any]:
            compiled = compile_onboarding_graph(saver)
            snapshot = self._snapshot(compiled, onboarding_id)
            return dict(snapshot.values)

        return with_checkpointer(self.paths.checkpoint, run)

    def hire_view(self, onboarding_id: str, hire_user_id: str) -> dict[str, Any]:
        record = self.current(onboarding_id)
        if record["hire_user_id"] != hire_user_id:
            raise OnboardingError("not_own_onboarding")
        view = dict(record)
        stage = int(record["current_stage"])
        if stage in CONTENT_STAGES and not (
            (stage == 2 and record["company_passed"])
            or (stage == 3 and record["operations_passed"])
            or (stage == 4 and record["compliance_approved"])
            or (stage == 5 and record["role_approved"])
            or (stage == 6 and record["how_we_work_passed"])
        ):
            view["content"] = presented_content(
                stage, framework=record["framework"], role_key=record["role_key"]
            )
            if record["pending_kind"] == "check":
                bank = record["active_bank"].get(str(stage), "a")
                view["questions"] = [
                    {
                        "id": item["id"],
                        "prompt": item["prompt"],
                        "choices": item["choices"],
                        "topic": item["topic"],
                        "source_document": item["source_document"],
                    }
                    for item in questions_for(
                        stage,
                        framework=record["framework"],
                        role_key=record["role_key"],
                        bank=bank,
                    )
                ]
        return view

    def people_list(self) -> list[dict[str, Any]]:
        rows = []
        for record in self.store.list_all():
            rows.append(
                {
                    "onboarding_id": record["onboarding_id"],
                    "display_name": record["display_name"],
                    "office": record["office"],
                    "department_id": record["department_id"],
                    "current_stage": record["current_stage"],
                    "stage_name": record["stage_name"],
                    "status": record["status"],
                    "pending_kind": record["pending_kind"],
                    "blocked": record["blocked"],
                    "last_action": record["last_action"],
                    "decision_nonce": record["decision_nonce"],
                    "last_rejection_comment": record["last_rejection_comment"],
                }
            )
        return rows

    def ask(self, onboarding_id: str, question: str, hire_user_id: str) -> dict[str, Any]:
        record = self.current(onboarding_id)
        if record["hire_user_id"] != hire_user_id:
            raise OnboardingError("not_own_onboarding")
        scan_mapping({"question": question})
        grounded = answer_question(
            question,
            framework=record["framework"],
            role_key=record["role_key"],
        )
        payload = {
            "covered": grounded.covered,
            "answer": grounded.answer,
            "source_document": grounded.source_document,
            "source_heading": grounded.source_heading,
            "route_to": grounded.route_to,
        }
        self.audit.write(
            "question_answered" if grounded.covered else "question_routed",
            onboarding_id=onboarding_id,
            stage=record["current_stage"],
            source_document=grounded.source_document or "uncovered",
            route_to=grounded.route_to or "",
        )
        if grounded.route_to:
            self._notice(
                "uncovered_question",
                grounded.route_to,
                onboarding_id,
                record["current_stage"],
                "uncovered_question",
            )
        return payload

    def request_access(self, onboarding_id: str, system_id: str, hire_user_id: str) -> dict[str, Any]:
        record = self.current(onboarding_id)
        if record["hire_user_id"] != hire_user_id:
            raise OnboardingError("not_own_onboarding")
        decision = evaluate_access_request(
            system_id, compliance_approved=bool(record["compliance_approved"])
        )
        row = {
            "id": uuid4().hex,
            "onboarding_id": onboarding_id,
            "system_id": system_id,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "security_event": decision.security_event,
        }
        self.store.append_access(row)
        if decision.security_event:
            self.audit.write(
                "security_early_access_denied",
                onboarding_id=onboarding_id,
                stage=record["current_stage"],
                system_id=system_id,
                reason=decision.reason,
            )
            self._notice(
                "security_event",
                "claire",
                onboarding_id,
                record["current_stage"],
                "early_patient_access_denied",
            )
            raise OnboardingError("patient_system_before_compliance_approval")
        if not decision.allowed:
            raise OnboardingError(decision.reason)
        self.audit.write(
            "access_request_recorded",
            onboarding_id=onboarding_id,
            stage=record["current_stage"],
            system_id=system_id,
        )
        return row

    def process_deadlines(self, onboarding_id: str) -> list[dict[str, Any]]:
        record = self.current(onboarding_id)
        if record["status"] == "complete":
            return []
        stage = int(record["current_stage"])
        reminders = dict(record.get("reminders_sent") or {})
        escalations = dict(record.get("escalations_sent") or {})
        timing = evaluate_stage_timing(
            record["start_date"],
            stage,
            self.clock.now(),
            self.calendar,
            reminder_already_sent=bool(reminders.get(str(stage))),
            escalation_already_sent=bool(escalations.get(str(stage))),
        )
        emitted: list[dict[str, Any]] = []
        if timing.reminder_due:
            emitted.append(
                self._notice("reminder", "hire", onboarding_id, stage, "stage_deadline_approaching")
            )
            reminders[str(stage)] = True
            self.audit.write("reminder_enqueued", onboarding_id=onboarding_id, stage=stage)
        if timing.overdue and not escalations.get(str(stage)):
            if stage == 4:
                recipient = "diane"
                template = "compliance_overdue_no_bypass"
            else:
                recipient = "manager"
                template = "stage_overdue"
            emitted.append(self._notice("escalation", recipient, onboarding_id, stage, template))
            escalations[str(stage)] = True
            self.audit.write(
                "escalation_enqueued",
                onboarding_id=onboarding_id,
                stage=stage,
                recipient=recipient,
            )
        record["reminders_sent"] = reminders
        record["escalations_sent"] = escalations
        self.store.upsert_onboarding(record)
        return emitted

    def process_all_deadlines(self) -> list[dict[str, Any]]:
        """Sweep every incomplete onboarding. Callers must not require HTTP."""
        emitted: list[dict[str, Any]] = []
        for record in self.store.list_all():
            if record.get("status") == "complete":
                continue
            emitted.extend(self.process_deadlines(record["onboarding_id"]))
        return emitted


def default_paths(root: Path) -> OnboardingPaths:
    directory = root / "data" / "process" / "onboarding"
    return OnboardingPaths(
        checkpoint=directory / "checkpoints.sqlite",
        store=directory / "store.json",
        audit=directory / "audit.jsonl",
        outbox=directory / "outbox.jsonl",
    )
