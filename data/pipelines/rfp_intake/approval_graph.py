"""Per-department approval interrupts. The parent thread does not interrupt.

Revenue, clinical, and compliance each have a checkpoint thread. Approving one
compiles that branch again and resumes it. The other checkpoints stay put.
"""

from __future__ import annotations

import contextvars
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from data.pipelines.rfp_intake.arbitration import (
    actor_may_resolve_capacity,
    assess_capacity,
    baa_dpa_targets,
    clinical_text,
    population_after_reduce,
    regulatory_blocks_capacity,
    section_has_phi,
)
from data.pipelines.rfp_intake.checkpointer import thread_id, with_checkpointer
from data.pipelines.rfp_intake.departments import DEPARTMENT_IDS, DEPARTMENTS
from data.pipelines.rfp_intake.evaluators import evaluate_compliance
from data.pipelines.rfp_intake.final_document import build_final_document
from data.pipelines.rfp_intake.generation import ChatComplete
from data.pipelines.rfp_intake.node_trace import append_trace
from data.pipelines.rfp_intake.response_loop import MAX_ATTEMPTS, run_department

_complete_fn: contextvars.ContextVar[ChatComplete | None] = contextvars.ContextVar(
    "rfp_approval_complete_fn",
    default=None,
)
_trace_records: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar(
    "rfp_approval_trace",
    default=None,
)


class ApprovalFlowError(Exception):
    """A decision the graph must not resume. code is safe to return to the client."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class BranchState(TypedDict):
    ticket_id: str
    department_id: str
    draft_content: str
    metadata: dict[str, Any]
    key_aspects: dict[str, Any]
    evaluation_results: dict[str, Any]
    decision: str
    note: str
    feedback: str
    approval_revision_count: int
    iteration_limit_reached: bool
    approved: bool


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _agent(department_id: str) -> str:
    return DEPARTMENTS[department_id]["contact_name"]


def _emit(node: str, agent: str, node_input: object, node_output: object) -> None:
    records = _trace_records.get()
    if records is None:
        return
    append_trace(records, node, agent, node_input, node_output)


def _await_approval(state: BranchState) -> dict[str, Any]:
    """Pause this department. On resume, interrupt() returns the human payload."""
    resumed = interrupt(
        {
            "ticket_id": state["ticket_id"],
            "department_id": state["department_id"],
            "draft_content": state["draft_content"],
        }
    )
    if not isinstance(resumed, dict):
        return {"decision": "", "note": "", "feedback": "", "approved": False}
    decision = resumed.get("decision")
    note = resumed.get("note")
    feedback = resumed.get("feedback")
    return {
        "decision": decision if isinstance(decision, str) else "",
        "note": note if isinstance(note, str) else "",
        "feedback": feedback if isinstance(feedback, str) else "",
        "approved": False,
    }


def _validate_decision(state: BranchState) -> dict[str, Any]:
    decision = state.get("decision") or ""
    count = int(state.get("approval_revision_count") or 0)
    limited = decision in {"reject", "request_changes"} and count >= MAX_ATTEMPTS
    approved = decision == "approve"
    _emit(
        "validate_decision",
        _agent(state["department_id"]),
        {
            "department_id": state["department_id"],
            "decision": decision,
            "approval_revision_count": count,
        },
        {
            "accepted": decision in {"approve", "reject", "request_changes"} and not limited,
            "approved": approved,
            "iteration_limit_reached": limited or bool(state.get("iteration_limit_reached")),
        },
    )
    return {
        "approved": approved,
        "iteration_limit_reached": limited or bool(state.get("iteration_limit_reached")),
    }


def _route_after_validate(state: BranchState) -> str:
    decision = state.get("decision") or ""
    if decision == "approve":
        return "approve"
    if decision not in {"reject", "request_changes"}:
        return "wait"
    if int(state.get("approval_revision_count") or 0) >= MAX_ATTEMPTS:
        return "wait"
    return "revise"


def _revise(state: BranchState) -> dict[str, Any]:
    """One Part 3 revision. Inner generator attempts do not add another count."""
    department_id = state["department_id"]
    complete = _complete_fn.get()
    if complete is None:
        raise ApprovalFlowError("generator_unavailable")
    previous_count = int(state.get("approval_revision_count") or 0)

    def on_node(event: dict[str, Any]) -> None:
        _emit(str(event["node"]), str(event["agent"]), event.get("input"), event.get("output"))

    outcome = run_department(
        department_id,
        state["metadata"],
        {"key_aspects": state["key_aspects"]},
        complete,
        on_node=on_node,
        feedback=state.get("feedback") or None,
    )
    draft = outcome["draft_content"] if isinstance(outcome.get("draft_content"), str) else ""
    evaluation = outcome["evaluation_results"] if isinstance(outcome.get("evaluation_results"), dict) else {}
    count = previous_count + 1
    _emit(
        f"revise_{department_id}",
        _agent(department_id),
        {
            "department_id": department_id,
            "approval_revision_count": previous_count,
            "feedback": state.get("feedback") or "",
        },
        {
            "draft_content": draft,
            "approval_revision_count": count,
            "needs_human_review": outcome.get("needs_human_review"),
        },
    )
    return {
        "draft_content": draft,
        "evaluation_results": evaluation,
        "approval_revision_count": count,
        "iteration_limit_reached": count >= MAX_ATTEMPTS,
        "approved": False,
        "decision": "",
    }


def _compile_branch(department_id: str, saver: Any):
    await_name = f"{department_id}_await_approval"
    revise_name = f"revise_{department_id}"
    graph = StateGraph(BranchState)
    graph.add_node(await_name, _await_approval)
    graph.add_node("validate_decision", _validate_decision)
    graph.add_node(revise_name, _revise)
    graph.set_entry_point(await_name)
    graph.add_edge(await_name, "validate_decision")
    graph.add_conditional_edges(
        "validate_decision",
        _route_after_validate,
        {"approve": END, "revise": revise_name, "wait": await_name},
    )
    graph.add_edge(revise_name, await_name)
    return graph.compile(checkpointer=saver)


def _config(ticket_id: str, department_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id(ticket_id, department_id)}}


def department_interrupted(path: Path, ticket_id: str, department_id: str) -> bool:
    """Read one branch from the checkpoint file. This compiles a new graph."""

    def read(saver: Any) -> bool:
        graph = _compile_branch(department_id, saver)
        snapshot = graph.get_state(_config(ticket_id, department_id))
        return bool(snapshot.next)

    return with_checkpointer(path, read)
    return {"configurable": {"thread_id": thread_id(ticket_id, department_id)}}


def _initial_state(ticket_id: str, section: dict[str, Any], metadata: dict[str, Any]) -> BranchState:
    draft = section.get("draft_content") if isinstance(section.get("draft_content"), str) else ""
    key_aspects = section.get("key_aspects") if isinstance(section.get("key_aspects"), dict) else {}
    evaluation = section.get("evaluation_results") if isinstance(section.get("evaluation_results"), dict) else {}
    return {
        "ticket_id": ticket_id,
        "department_id": section["department_id"],
        "draft_content": draft,
        "metadata": metadata,
        "key_aspects": key_aspects,
        "evaluation_results": evaluation,
        "decision": "",
        "note": "",
        "feedback": "",
        "approval_revision_count": int(section.get("approval_revision_count") or 0),
        "iteration_limit_reached": bool(section.get("iteration_limit_reached")),
        "approved": False,
    }


def _clear_approval(section: dict[str, Any]) -> None:
    section["approval_status"] = "pending"
    section["approver"] = None
    section["approved_at"] = None
    section["approved_content_sha256"] = None
    section["submitted_by_user_id"] = None


def _apply_graph_values(section: dict[str, Any], values: dict[str, Any]) -> None:
    draft = values.get("draft_content")
    if isinstance(draft, str) and draft != section.get("draft_content"):
        section["draft_content"] = draft
        _clear_approval(section)
    if isinstance(values.get("evaluation_results"), dict):
        section["evaluation_results"] = values["evaluation_results"]
    if isinstance(values.get("key_aspects"), dict):
        section["key_aspects"] = values["key_aspects"]
    section["approval_revision_count"] = int(values.get("approval_revision_count") or 0)
    section["iteration_limit_reached"] = bool(values.get("iteration_limit_reached"))


class ApprovalRun:
    """One ticket's Part 3 decisions. sections and trace are mutated in place."""

    def __init__(
        self,
        ticket_id: str,
        metadata: dict[str, Any],
        sections: list[dict[str, Any]],
        handoff: dict[str, Any],
        trace: list[dict[str, Any]],
        checkpoint_path: Path,
        complete_fn: ChatComplete,
        *,
        phi_detected: bool = False,
        arbitration: dict[str, Any] | None = None,
    ) -> None:
        self.ticket_id = ticket_id
        self.metadata = metadata
        self.sections = sections
        self.handoff = handoff
        self.trace = trace
        self.checkpoint_path = checkpoint_path
        self.complete_fn = complete_fn
        self.phi_detected = phi_detected
        self.arbitration = arbitration if isinstance(arbitration, dict) else {}
        self.final_document: dict[str, Any] | None = None

    def section(self, department_id: str) -> dict[str, Any]:
        for item in self.sections:
            if item.get("department_id") == department_id:
                return item
        raise ApprovalFlowError("unknown_department")

    def start(self) -> None:
        """Open each branch once. A second call leaves counts and checkpoints as they are."""
        if all(self._is_interrupted(department_id) for department_id in DEPARTMENT_IDS):
            return
        _emit_on(
            self.trace,
            "enter_part3",
            "Revenue Cycle",
            {"thread_id": thread_id(self.ticket_id)},
            {"status": "waiting_for_approval"},
        )
        for department_id in DEPARTMENT_IDS:
            self._ensure_interrupted(department_id)
        self._refresh_arbitration(force=True)

    def decide(
        self,
        department_id: str,
        *,
        actor_department_id: str,
        submitted_by_user_id: str,
        approver_name: str,
        decision: str,
        note: str | None,
    ) -> None:
        if actor_department_id != department_id:
            raise ApprovalFlowError("not_department_owner")
        if decision not in {"approve", "reject", "request_changes"}:
            raise ApprovalFlowError("invalid_decision")
        if decision in {"reject", "request_changes"} and not (note or "").strip():
            raise ApprovalFlowError("note_required")
        if not self._is_interrupted(department_id):
            raise ApprovalFlowError("not_interrupted")
        section = self.section(department_id)
        if decision in {"reject", "request_changes"} and int(section.get("approval_revision_count") or 0) >= MAX_ATTEMPTS:
            section["iteration_limit_reached"] = True
            raise ApprovalFlowError("iteration_limit_reached")
        if decision == "approve":
            reason = self._approve_block_reason(department_id)
            if reason is not None:
                raise ApprovalFlowError(reason)
        feedback = (note or "").strip()
        self._resume(
            department_id,
            {"decision": decision, "note": note or "", "feedback": feedback},
        )
        if decision == "approve" and self._branch_approved(department_id):
            self._mark_approved(section, submitted_by_user_id, approver_name)
        self._refresh_arbitration(force=False)
        self._converge()

    def resolve_capacity(self, *, actor_department_id: str, resolution: str) -> None:
        if not actor_may_resolve_capacity(actor_department_id):
            raise ApprovalFlowError("not_capacity_arbiter")
        if resolution not in {"reduce_covered_population", "add_sites"}:
            raise ApprovalFlowError("invalid_resolution")
        capacity = self.arbitration.get("capacity") if isinstance(self.arbitration.get("capacity"), dict) else None
        if capacity is None or capacity.get("resolved") is True:
            raise ApprovalFlowError("resolution_not_open")
        if regulatory_blocks_capacity(
            bool(self.arbitration.get("phi_detected")),
            bool(self.arbitration.get("baa_dpa_mismatch")),
        ):
            raise ApprovalFlowError("arbitration_unresolved")
        target = "revenue" if resolution == "reduce_covered_population" else "clinical"
        section = self.section(target)
        if int(section.get("approval_revision_count") or 0) >= MAX_ATTEMPTS:
            section["iteration_limit_reached"] = True
            raise ApprovalFlowError("iteration_limit_reached")
        if resolution == "reduce_covered_population":
            coverage = capacity.get("coverage") if isinstance(capacity.get("coverage"), dict) else None
            if coverage is None or "count" not in coverage or "unit" not in coverage:
                raise ApprovalFlowError("resolution_not_open")
            updated_population = population_after_reduce(coverage)
            self.metadata["covered_population"] = updated_population
            self.handoff["covered_population"] = updated_population
            feedback = (
                f"State the covered population as {coverage['count']} {coverage['unit']}. "
                "That figure is already in the clinical coverage sentence. Do not invent a different headcount."
            )
        else:
            population = self.metadata.get("covered_population")
            feedback = (
                "Add sites so this section states coverage for the population already on the ticket: "
                f"{population}. Do not invent a site count. State an explicit coverage figure using the "
                "same unit as that population."
            )
        capacity["resolution"] = resolution
        _emit_on(
            self.trace,
            "capacity_choice",
            "Tom Callahan",
            {"resolution": resolution, "department_id": target},
            {"covered_population": self.metadata.get("covered_population"), "wrote_new_integer": False},
        )
        self._resume(target, {"decision": "request_changes", "note": feedback, "feedback": feedback})
        self._refresh_arbitration(force=False)

    def _ensure_interrupted(self, department_id: str) -> None:
        if self._is_interrupted(department_id):
            return
        section = self.section(department_id)
        if section.get("approval_status") is None:
            section["approval_status"] = "pending"
            section["approval_revision_count"] = int(section.get("approval_revision_count") or 0)

        def invoke(saver: Any) -> Any:
            graph = _compile_branch(department_id, saver)
            return graph.invoke(
                _initial_state(self.ticket_id, section, self.metadata),
                _config(self.ticket_id, department_id),
            )

        self._call_graph(invoke)
        self._trace_wait(department_id)

    def _is_interrupted(self, department_id: str) -> bool:
        def read(saver: Any) -> bool:
            graph = _compile_branch(department_id, saver)
            snapshot = graph.get_state(_config(self.ticket_id, department_id))
            return bool(snapshot.next)

        return self._call_graph(read)

    def _branch_approved(self, department_id: str) -> bool:
        def read(saver: Any) -> bool:
            graph = _compile_branch(department_id, saver)
            snapshot = graph.get_state(_config(self.ticket_id, department_id))
            return not snapshot.next and bool(snapshot.values.get("approved"))

        return self._call_graph(read)

    def _resume(self, department_id: str, payload: dict[str, str]) -> None:
        if not self._is_interrupted(department_id):
            raise ApprovalFlowError("not_interrupted")

        section = self.section(department_id)

        def invoke(saver: Any) -> Any:
            graph = _compile_branch(department_id, saver)
            config = _config(self.ticket_id, department_id)
            # The checkpoint keeps the metadata from the first interrupt. Copy the
            # current ticket fields in so a capacity resolution is visible to revise.
            graph.update_state(
                config,
                {
                    "metadata": self.metadata,
                    "draft_content": section.get("draft_content") or "",
                    "evaluation_results": section.get("evaluation_results") or {},
                    "key_aspects": section.get("key_aspects") or {},
                    "approval_revision_count": int(section.get("approval_revision_count") or 0),
                },
            )
            graph.invoke(Command(resume=payload), config)
            return graph.get_state(config)

        snapshot = self._call_graph(invoke)
        _apply_graph_values(self.section(department_id), snapshot.values)
        if snapshot.next:
            self._trace_wait(department_id)

    def _call_graph(self, use: Any) -> Any:
        token_complete = _complete_fn.set(self.complete_fn)
        token_trace = _trace_records.set(self.trace)
        try:
            return with_checkpointer(self.checkpoint_path, use)
        finally:
            _complete_fn.reset(token_complete)
            _trace_records.reset(token_trace)

    def _trace_wait(self, department_id: str) -> None:
        section = self.section(department_id)
        _emit_on(
            self.trace,
            f"{department_id}_await_approval",
            _agent(department_id),
            {
                "department_id": department_id,
                "thread_id": thread_id(self.ticket_id, department_id),
                "draft_content": section.get("draft_content") or "",
            },
            {"interrupted": True},
        )

    def _mark_approved(self, section: dict[str, Any], submitted_by_user_id: str, approver_name: str) -> None:
        draft = section.get("draft_content") if isinstance(section.get("draft_content"), str) else ""
        section["approval_status"] = "approved"
        section["approver"] = approver_name
        section["approved_at"] = datetime.now(UTC).isoformat()
        section["approved_content_sha256"] = content_sha256(draft)
        section["submitted_by_user_id"] = submitted_by_user_id

    def _approve_block_reason(self, department_id: str) -> str | None:
        section = self.section(department_id)
        if self.phi_detected or section_has_phi(section):
            return "approval_checks_failed"
        draft = section.get("draft_content") if isinstance(section.get("draft_content"), str) else ""
        compliance = evaluate_compliance(draft, department_id, self.metadata)
        if not compliance.get("pass"):
            return "approval_checks_failed"
        capacity = self.arbitration.get("capacity") if isinstance(self.arbitration.get("capacity"), dict) else None
        if capacity is not None and capacity.get("resolved") is not True and department_id in {"revenue", "clinical"}:
            return "arbitration_unresolved"
        # Read the current drafts. The stored target list can remain after the
        # sentence that opened it was rewritten as a rejection of that instrument.
        targets = baa_dpa_targets(self.metadata.get("client_country"), self.sections)
        if department_id in targets:
            return "approval_checks_failed"
        return None

    def _refresh_arbitration(self, *, force: bool) -> None:
        country = self.metadata.get("client_country")
        clinical = self.section("clinical")
        established = self.arbitration.get("capacity") if isinstance(self.arbitration.get("capacity"), dict) else None
        phi_open = self.phi_detected or any(section_has_phi(section) for section in self.sections)
        targets = baa_dpa_targets(country, self.sections)
        baa_open = bool(targets)
        questions, capacity = assess_capacity(
            self.metadata.get("covered_population"),
            clinical_text(clinical),
            established,
        )
        if regulatory_blocks_capacity(phi_open, baa_open) and established is None:
            capacity = None
        self.phi_detected = phi_open
        self.arbitration = {
            "phi_detected": phi_open,
            "baa_dpa_mismatch": baa_open,
            "baa_targets": targets,
            "capacity": capacity,
            "open_questions": questions,
        }
        if phi_open or baa_open or (capacity is not None and capacity.get("resolved") is not True):
            arbiter = "Claire Whitfield" if phi_open or baa_open else "Tom Callahan"
            _emit_on(
                self.trace,
                "arbitrate",
                arbiter,
                {
                    "phi_detected": phi_open,
                    "baa_dpa_mismatch": baa_open,
                    "capacity": capacity,
                },
                {"baa_targets": targets, "capacity_resolved": bool(capacity and capacity.get("resolved"))},
            )
        if not force:
            return
        if phi_open:
            phi_targets = [
                section["department_id"]
                for section in self.sections
                if isinstance(section.get("department_id"), str) and section_has_phi(section)
            ]
            self._force_revision(
                phi_targets or ["compliance"],
                "Remove patient identifiers. The section cannot be approved while PHI is present.",
            )
            return
        if baa_open:
            self._force_revision(
                targets,
                "Request changes until the country-correct BAA or DPA clause is in the section.",
            )

    def _force_revision(self, department_ids: list[str], feedback: str) -> None:
        """One arbitration revision per target. A later pass does not stack another force."""
        for department_id in department_ids:
            if department_id not in DEPARTMENT_IDS:
                continue
            section = self.section(department_id)
            if int(section.get("approval_revision_count") or 0) >= MAX_ATTEMPTS:
                section["iteration_limit_reached"] = True
                continue
            if not self._is_interrupted(department_id):
                continue
            self._resume(
                department_id,
                {"decision": "request_changes", "note": feedback, "feedback": feedback},
            )

    def _converge(self) -> None:
        missing = [department_id for department_id in DEPARTMENT_IDS if not self._section_eligible(department_id)]
        eligible = not missing and not self.phi_detected
        capacity = self.arbitration.get("capacity") if isinstance(self.arbitration.get("capacity"), dict) else None
        if capacity is not None and capacity.get("resolved") is not True:
            eligible = False
        if self.arbitration.get("baa_dpa_mismatch"):
            eligible = False
        _emit_on(
            self.trace,
            "converge_eligibility",
            "Revenue Cycle",
            {"ticket_id": self.ticket_id},
            {"eligible": eligible, "missing": missing},
        )
        if not eligible or self.final_document is not None:
            return
        ordered = []
        for department_id in DEPARTMENT_IDS:
            section = self.section(department_id)
            draft = section.get("draft_content") if isinstance(section.get("draft_content"), str) else ""
            ordered.append({"department_id": department_id, "draft_content": draft})
        currency = self.handoff.get("currency") if isinstance(self.handoff.get("currency"), str) else None
        document = build_final_document(self.ticket_id, ordered, currency, datetime.now(UTC))
        _emit_on(
            self.trace,
            "synthesize_final_document",
            "final_synthesizer",
            {"departments": list(DEPARTMENT_IDS)},
            {"sections": document["sections"], "currency": currency},
        )
        _emit_on(
            self.trace,
            "persist_document_and_done",
            "document_store",
            {"ticket_id": self.ticket_id},
            {"status": "done", "currency": currency},
        )
        self.final_document = document

    def _section_eligible(self, department_id: str) -> bool:
        section = self.section(department_id)
        if section.get("approval_status") != "approved":
            return False
        draft = section.get("draft_content") if isinstance(section.get("draft_content"), str) else ""
        if section.get("approved_content_sha256") != content_sha256(draft):
            _clear_approval(section)
            return False
        if department_id == "compliance" and section.get("approval_status") != "approved":
            return False
        return self._approve_block_reason(department_id) is None


def _emit_on(
    records: list[dict[str, Any]],
    node: str,
    agent: str,
    node_input: object,
    node_output: object,
) -> None:
    append_trace(records, node, agent, node_input, node_output)
