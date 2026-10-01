"""Persist intake results and run the pipeline off the request thread."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.rfp_models import DepartmentSection, RfpMetadata, RfpTicket, utc_now
from app.schemas.rfp import (
    DepartmentSectionPublic,
    RfpMetadataPublic,
    RfpTicketPublic,
)
from data.pipelines.rfp_intake.generation import ChatComplete, ModelAssetMissing, PipelineFailure, complete_local
from data.pipelines.rfp_intake.phi import screen_structure
from data.pipelines.rfp_intake.readiness import assess_readiness
from data.pipelines.rfp_intake.response_loop import run_response_generation
from data.pipelines.rfp_intake.runner import IntakeRun, process_pdf

logger = logging.getLogger("healthcore.rfp_intake")


class ResponseNotReady(Exception):
    """The ticket cannot enter Part 2. The code is safe to return to the client."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

STALE_AFTER = timedelta(minutes=15)
RUNNING_TICKETS: set[str] = set()
_RESPONSE_LOCK = threading.Lock()
# Test hooks. Production leaves both unset, so the pipeline uses local llama.cpp
# and data/raw/rfp_intake. A background task can read these because they are
# process state, not a request-scoped context variable.
complete_override_fn: ChatComplete | None = None
storage_override: Path | None = None
checkpoint_override: Path | None = None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def create_ticket(session: Session) -> RfpTicket:
    """Insert an analyzing ticket and commit it before the upload response returns."""
    now = utc_now()
    ticket = RfpTicket(
        ticket_id=str(uuid.uuid4()),
        status="analyzing",
        created_at=now,
        updated_at=now,
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def begin_response(session: Session, ticket_id: str) -> RfpTicket:
    """Mark one ready ticket as drafting. Do not open the PDF or rebuild the summary."""
    ticket = session.get(RfpTicket, ticket_id)
    if ticket is None:
        raise ResponseNotReady("ticket_missing")
    decision = assess_readiness(ticket.status, ticket.ticket_id, ticket.part2_handoff)
    if not decision.accepted:
        raise ResponseNotReady(decision.reason or "not_intake_complete")
    ticket.status = "drafting"
    ticket.processing_failed = False
    ticket.processing_error_code = None
    ticket.updated_at = utc_now()
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def _complete_for_response(messages: list[dict[str, str]]) -> str:
    if complete_override_fn is not None:
        return complete_override_fn(messages)
    return complete_local(messages)


def _mark_response_failed(ticket_id: str, code: str) -> None:
    logger.error("rfp_response_failed code=%s", code)
    with _RESPONSE_LOCK:
        with Session(session_bind()) as session:
            ticket = session.get(RfpTicket, ticket_id)
            if ticket is None or _response_is_complete(ticket):
                return
            ticket.processing_failed = True
            ticket.processing_error_code = code
            ticket.updated_at = utc_now()
            session.add(ticket)
            session.commit()


def _response_is_complete(ticket: RfpTicket) -> bool:
    handoff = ticket.part3_handoff
    return isinstance(handoff, dict) and handoff.get("response_complete") is True


def session_bind():
    """The API engine. Tests patch this only by replacing get_engine's database."""
    from app.db.database import get_engine

    return get_engine()


def _apply_progress(ticket_id: str, event: dict[str, Any]) -> None:
    """Move drafting to under_evaluation once any department is being checked.

    A provisional section does not finish the ticket. That write waits until
    every department has returned.
    """
    if event.get("phase") != "under_evaluation":
        return
    with _RESPONSE_LOCK:
        with Session(session_bind()) as session:
            ticket = session.get(RfpTicket, ticket_id)
            if ticket is None or ticket.status != "drafting" or _response_is_complete(ticket):
                return
            ticket.status = "under_evaluation"
            ticket.updated_at = utc_now()
            session.add(ticket)
            session.commit()


def _append_response_trace(ticket_id: str, event: dict[str, Any]) -> None:
    """Record one Part 2 generate or evaluate step under the response lock."""
    from data.pipelines.rfp_intake.node_trace import append_trace

    with _RESPONSE_LOCK:
        with Session(session_bind()) as session:
            ticket = session.get(RfpTicket, ticket_id)
            if ticket is None:
                return
            records = list(ticket.node_trace or [])
            append_trace(records, str(event["node"]), str(event["agent"]), event.get("input"), event.get("output"))
            ticket.node_trace = records
            ticket.updated_at = utc_now()
            session.add(ticket)
            session.commit()


def _store_department_outcome(ticket_id: str, outcome: dict[str, Any]) -> None:
    """Save one finished section while other departments may still be running."""
    department_id = outcome.get("department_id")
    if not isinstance(department_id, str):
        return
    with _RESPONSE_LOCK:
        with Session(session_bind()) as session:
            ticket = session.get(RfpTicket, ticket_id)
            if ticket is None or _response_is_complete(ticket):
                return
            section = session.exec(
                select(DepartmentSection).where(
                    DepartmentSection.ticket_id == ticket_id,
                    DepartmentSection.department_id == department_id,
                )
            ).first()
            if section is None:
                section = DepartmentSection(ticket_id=ticket_id, department_id=department_id)
            section.draft_content = outcome.get("draft_content") if isinstance(outcome.get("draft_content"), str) else ""
            evaluation = outcome.get("evaluation_results")
            section.evaluation_results = evaluation if isinstance(evaluation, dict) else {}
            section.needs_human_review = bool(outcome.get("needs_human_review"))
            if section.evaluation_results.get("contains_phi"):
                ticket.phi_detected = True
                ticket.compliance_review_required = True
            ticket.updated_at = utc_now()
            session.add(section)
            session.add(ticket)
            session.commit()


def run_response(session: Session, ticket_id: str) -> None:
    """Generate and evaluate on the ticket Part 1 already stored."""
    RUNNING_TICKETS.add(ticket_id)
    try:
        ticket = session.get(RfpTicket, ticket_id)
        if ticket is None or not isinstance(ticket.part2_handoff, dict):
            _mark_response_failed(ticket_id, "handoff_missing")
            return
        handoff = run_response_generation(
            ticket.part2_handoff,
            _complete_for_response,
            on_progress=lambda event: _apply_progress(ticket_id, event),
            on_department_done=lambda outcome: _store_department_outcome(ticket_id, outcome),
            on_node=lambda event: _append_response_trace(ticket_id, event),
        )
        with _RESPONSE_LOCK:
            with Session(session_bind()) as write_session:
                stored = write_session.get(RfpTicket, ticket_id)
                if stored is None:
                    return
                stored.part3_handoff = handoff
                provisional = any(
                    isinstance(section, dict) and section.get("needs_human_review")
                    for section in handoff.get("sections", [])
                )
                stored.status = "needs_human_review" if provisional else "under_evaluation"
                if handoff.get("phi_detected"):
                    stored.phi_detected = True
                    stored.compliance_review_required = True
                stored.processing_failed = False
                stored.processing_error_code = None
                stored.updated_at = utc_now()
                write_session.add(stored)
                write_session.commit()
    except ModelAssetMissing:
        _mark_response_failed(ticket_id, "model_asset_missing")
    except PipelineFailure as exc:
        _mark_response_failed(ticket_id, exc.code)
    except Exception:
        _mark_response_failed(ticket_id, "pipeline_exception")
    finally:
        RUNNING_TICKETS.discard(ticket_id)


def _touch(session: Session, ticket: RfpTicket) -> None:
    ticket.updated_at = utc_now()
    session.add(ticket)
    session.commit()


def _apply_run(session: Session, ticket: RfpTicket, result: IntakeRun) -> None:
    """Commit status, handoff, metadata, and sections together.

    A reader polls until status is intake_complete and then stops. That status
    has to become visible in the same commit as the rows the page renders.
    Flushing the deletes first keeps the metadata unique key valid without
    opening a second transaction.
    """
    ticket.status = result.status
    ticket.processing_failed = result.processing_failed
    ticket.processing_error_code = result.error_code
    ticket.phi_detected = result.phi_detected
    ticket.compliance_review_required = result.compliance_review_required
    ticket.raw_pdf_path = result.raw_pdf_path
    ticket.part2_handoff = result.handoff
    ticket.node_trace = list(result.node_trace or [])
    ticket.updated_at = utc_now()
    session.add(ticket)

    existing_metadata = session.exec(
        select(RfpMetadata).where(RfpMetadata.ticket_id == ticket.ticket_id)
    ).first()
    if existing_metadata is not None:
        session.delete(existing_metadata)
    for section in session.exec(
        select(DepartmentSection).where(DepartmentSection.ticket_id == ticket.ticket_id)
    ).all():
        session.delete(section)
    session.flush()

    if result.metadata is not None:
        metrics = result.readability or {}
        metadata = RfpMetadata(
            ticket_id=ticket.ticket_id,
            client_name=result.metadata.get("client_name"),
            client_country=result.metadata.get("client_country"),
            program_type=result.metadata.get("program_type"),
            covered_population=result.metadata.get("covered_population"),
            deadline=result.metadata.get("deadline"),
            budget_range=result.metadata.get("budget_range"),
            departments_needed=result.metadata.get("departments_needed") or [],
            flesch_kincaid_grade=metrics.get("flesch_kincaid_grade"),
            gunning_fog=metrics.get("gunning_fog"),
        )
        session.add(metadata)
        for section in result.sections:
            session.add(
                DepartmentSection(
                    ticket_id=ticket.ticket_id,
                    department_id=section["department_id"],
                    key_aspects={
                        "aspects": section.get("aspects") or [],
                        "open_questions": section.get("open_questions") or [],
                        "department_name": section.get("department_name"),
                        "contact_name": section.get("contact_name"),
                    },
                )
            )
    session.commit()


def run_ticket(session: Session, ticket_id: str, pdf_bytes: bytes) -> None:
    """Background entry. Failures stay on analyzing and do not store exception text."""
    RUNNING_TICKETS.add(ticket_id)
    try:
        ticket = session.get(RfpTicket, ticket_id)
        if ticket is None:
            logger.error("rfp_intake_failed code=ticket_missing")
            return
        _touch(session, ticket)
        result = process_pdf(
            pdf_bytes,
            ticket_id,
            complete_fn=complete_override_fn,
            storage_dir=storage_override,
        )
        stored = session.get(RfpTicket, ticket_id)
        if stored is None:
            return
        _apply_run(session, stored, result)
    except Exception:
        logger.error("rfp_intake_failed code=pipeline_exception")
        stored = session.get(RfpTicket, ticket_id)
        if stored is not None:
            stored.status = "analyzing"
            stored.processing_failed = True
            stored.processing_error_code = "pipeline_exception"
            stored.updated_at = utc_now()
            session.add(stored)
            session.commit()
    finally:
        RUNNING_TICKETS.discard(ticket_id)


def _stalled(ticket: RfpTicket) -> bool:
    if ticket.status != "analyzing" or ticket.processing_failed:
        return False
    if ticket.ticket_id in RUNNING_TICKETS:
        return False
    return _as_utc(ticket.updated_at) < datetime.now(UTC) - STALE_AFTER


def _public_from_rows(
    ticket: RfpTicket,
    metadata: RfpMetadata | None,
    sections: list[DepartmentSection],
) -> RfpTicketPublic:
    summary = None
    if isinstance(ticket.part2_handoff, dict):
        raw_summary = ticket.part2_handoff.get("synthesizer_summary")
        summary = raw_summary if isinstance(raw_summary, str) else None
    metadata_public = None
    if metadata is not None:
        metadata_public = RfpMetadataPublic(
            client_name=metadata.client_name,
            client_country=metadata.client_country,
            program_type=metadata.program_type,
            covered_population=metadata.covered_population,
            deadline=metadata.deadline,
            budget_range=metadata.budget_range,
            departments_needed=list(metadata.departments_needed or []),
            flesch_kincaid_grade=metadata.flesch_kincaid_grade,
            gunning_fog=metadata.gunning_fog,
        )
    section_public = [
        DepartmentSectionPublic(
            department_id=section.department_id,
            department_name=(section.key_aspects or {}).get("department_name"),
            contact_name=(section.key_aspects or {}).get("contact_name"),
            key_aspects={
                "aspects": (section.key_aspects or {}).get("aspects") or [],
                "open_questions": (section.key_aspects or {}).get("open_questions") or [],
            },
            draft_content=section.draft_content,
            evaluation_results=section.evaluation_results,
            needs_human_review=section.needs_human_review,
            approval_status=section.approval_status,
            approver=section.approver,
            approved_at=section.approved_at,
            approved_content_sha256=section.approved_content_sha256,
            submitted_by_user_id=section.submitted_by_user_id,
            approval_revision_count=section.approval_revision_count,
            iteration_limit_reached=section.iteration_limit_reached,
        )
        for section in sections
    ]
    payload: dict[str, Any] = {
        "summary": summary,
        "metadata": metadata_public.model_dump() if metadata_public else None,
        "sections": [item.model_dump() for item in section_public],
        "handoff": ticket.part2_handoff,
        "part3_handoff": ticket.part3_handoff,
        "node_trace": ticket.node_trace,
        "arbitration_state": ticket.arbitration_state,
    }
    # Last gate before the response. Persistence already screened these fields.
    screened, _detected, _blocked = screen_structure(payload)
    assert isinstance(screened, dict)
    return RfpTicketPublic(
        ticket_id=ticket.ticket_id,
        status=ticket.status,
        raw_pdf_path=ticket.raw_pdf_path,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        processing_failed=ticket.processing_failed,
        processing_error_code=ticket.processing_error_code,
        stalled=_stalled(ticket),
        phi_detected=ticket.phi_detected,
        compliance_review_required=ticket.compliance_review_required,
        metadata=RfpMetadataPublic(**screened["metadata"]) if screened["metadata"] else None,
        sections=[DepartmentSectionPublic(**item) for item in screened["sections"]],
        synthesizer_summary=screened["summary"],
        part2_handoff=screened["handoff"],
        part3_handoff=screened["part3_handoff"],
        node_trace=screened.get("node_trace"),
        arbitration_state=screened.get("arbitration_state"),
    )


def get_ticket(session: Session, ticket_id: str) -> RfpTicketPublic | None:
    ticket = session.get(RfpTicket, ticket_id)
    if ticket is None:
        return None
    metadata = session.exec(select(RfpMetadata).where(RfpMetadata.ticket_id == ticket_id)).first()
    sections = list(
        session.exec(select(DepartmentSection).where(DepartmentSection.ticket_id == ticket_id)).all()
    )
    return _public_from_rows(ticket, metadata, sections)


class ApprovalNotAccepted(Exception):
    """Part 3 refused the call. code is safe to show to the client."""

    def __init__(self, code: str, status_code: int = 409) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def _approval_status_code(code: str) -> int:
    if code in {"not_department_owner", "not_capacity_arbiter"}:
        return 403
    if code in {"invalid_decision", "note_required", "invalid_resolution", "unknown_department"}:
        return 422
    return 409


def _parse_approved_at(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value)
    return None


def _checkpoint_path() -> Path:
    from data.pipelines.rfp_intake.checkpointer import CHECKPOINT_PATH

    return checkpoint_override or CHECKPOINT_PATH


def _section_state(section: DepartmentSection) -> dict[str, Any]:
    return {
        "department_id": section.department_id,
        "draft_content": section.draft_content or "",
        "evaluation_results": dict(section.evaluation_results or {}),
        "key_aspects": dict(section.key_aspects or {}),
        "needs_human_review": section.needs_human_review,
        "approval_status": section.approval_status,
        "approver": section.approver,
        "approved_at": section.approved_at.isoformat() if section.approved_at else None,
        "approved_content_sha256": section.approved_content_sha256,
        "submitted_by_user_id": section.submitted_by_user_id,
        "approval_revision_count": section.approval_revision_count or 0,
        "iteration_limit_reached": section.iteration_limit_reached,
    }


def _write_section(section: DepartmentSection, state: dict[str, Any]) -> None:
    section.draft_content = state.get("draft_content") if isinstance(state.get("draft_content"), str) else ""
    evaluation = state.get("evaluation_results")
    section.evaluation_results = dict(evaluation) if isinstance(evaluation, dict) else {}
    key_aspects = state.get("key_aspects")
    section.key_aspects = dict(key_aspects) if isinstance(key_aspects, dict) else {}
    section.needs_human_review = bool(state.get("needs_human_review"))
    section.approval_status = state.get("approval_status") if isinstance(state.get("approval_status"), str) else None
    section.approver = state.get("approver") if isinstance(state.get("approver"), str) else None
    section.approved_at = _parse_approved_at(state.get("approved_at"))
    digest = state.get("approved_content_sha256")
    section.approved_content_sha256 = digest if isinstance(digest, str) else None
    submitted = state.get("submitted_by_user_id")
    section.submitted_by_user_id = submitted if isinstance(submitted, str) else None
    section.approval_revision_count = int(state.get("approval_revision_count") or 0)
    section.iteration_limit_reached = bool(state.get("iteration_limit_reached"))


def _metadata_state(metadata: RfpMetadata | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    return {
        "client_name": metadata.client_name,
        "client_country": metadata.client_country,
        "program_type": metadata.program_type,
        "covered_population": metadata.covered_population,
        "deadline": metadata.deadline,
        "budget_range": metadata.budget_range,
        "departments_needed": list(metadata.departments_needed or []),
    }


def _load_approval_rows(session: Session, ticket_id: str) -> tuple[RfpTicket, RfpMetadata | None, list[DepartmentSection]]:
    ticket = session.get(RfpTicket, ticket_id)
    if ticket is None:
        raise ApprovalNotAccepted("ticket_missing", 404)
    metadata = session.exec(select(RfpMetadata).where(RfpMetadata.ticket_id == ticket_id)).first()
    sections = list(
        session.exec(select(DepartmentSection).where(DepartmentSection.ticket_id == ticket_id)).all()
    )
    return ticket, metadata, sections


def _persist_approval(
    session: Session,
    ticket: RfpTicket,
    metadata: RfpMetadata | None,
    rows: list[DepartmentSection],
    run: Any,
) -> None:
    from app.rfp_models import RfpFinalDocument

    by_id = {row.department_id: row for row in rows}
    for state in run.sections:
        row = by_id.get(state["department_id"])
        if row is None:
            continue
        _write_section(row, state)
        session.add(row)
    if metadata is not None:
        metadata.covered_population = run.metadata.get("covered_population")
        session.add(metadata)
    ticket.part3_handoff = dict(run.handoff)
    ticket.node_trace = list(run.trace)
    ticket.arbitration_state = dict(run.arbitration)
    if run.phi_detected:
        ticket.phi_detected = True
        ticket.compliance_review_required = True
    document = run.final_document
    if document is not None:
        existing = session.get(RfpFinalDocument, ticket.ticket_id)
        if existing is None:
            session.add(
                RfpFinalDocument(
                    ticket_id=ticket.ticket_id,
                    sections=document["sections"],
                    currency=document["currency"],
                    generated_at=document["generated_at"],
                )
            )
        ticket.status = "done"
    ticket.updated_at = utc_now()
    session.add(ticket)
    session.commit()


def _approval_run(ticket: RfpTicket, metadata: RfpMetadata | None, rows: list[DepartmentSection]) -> Any:
    from data.pipelines.rfp_intake.approval_graph import ApprovalRun
    from data.pipelines.rfp_intake.departments import DEPARTMENT_IDS

    by_id = {row.department_id: row for row in rows}
    if any(department_id not in by_id for department_id in DEPARTMENT_IDS):
        raise ApprovalNotAccepted("not_ready")
    ordered = [_section_state(by_id[department_id]) for department_id in DEPARTMENT_IDS]
    handoff = dict(ticket.part3_handoff or {})
    return ApprovalRun(
        ticket.ticket_id,
        _metadata_state(metadata),
        ordered,
        handoff,
        list(ticket.node_trace or []),
        _checkpoint_path(),
        _complete_for_response,
        phi_detected=ticket.phi_detected,
        arbitration=dict(ticket.arbitration_state or {}),
    )


def _require_ready(ticket: RfpTicket) -> None:
    handoff = ticket.part3_handoff
    if not isinstance(handoff, dict) or handoff.get("response_complete") is not True:
        raise ApprovalNotAccepted("response_incomplete")
    if ticket.status == "done":
        raise ApprovalNotAccepted("already_done")
    if ticket.status not in {"under_evaluation", "needs_human_review", "waiting_for_approval"}:
        raise ApprovalNotAccepted("not_ready")


def begin_approval(session: Session, ticket_id: str) -> RfpTicket:
    """Pause each department. Repeating this call does not reset counts or checkpoints."""
    from data.pipelines.rfp_intake.approval_graph import ApprovalFlowError

    with _RESPONSE_LOCK:
        ticket, metadata, rows = _load_approval_rows(session, ticket_id)
        _require_ready(ticket)
        ticket.status = "waiting_for_approval"
        try:
            run = _approval_run(ticket, metadata, rows)
            run.start()
        except ApprovalFlowError as exc:
            raise ApprovalNotAccepted(exc.code, _approval_status_code(exc.code)) from exc
        _persist_approval(session, ticket, metadata, rows, run)
        session.refresh(ticket)
        return ticket


def submit_approval_decision(
    session: Session,
    ticket_id: str,
    department_id: str,
    *,
    user_id: str,
    decision: str | None,
    note: str | None,
    resolution: str | None,
) -> None:
    """Resume one branch, or record Tom Callahan's capacity choice."""
    from app.rfp_models import RfpDepartmentAccount
    from data.pipelines.rfp_intake.approval_graph import ApprovalFlowError

    with _RESPONSE_LOCK:
        ticket, metadata, rows = _load_approval_rows(session, ticket_id)
        if ticket.status == "done":
            raise ApprovalNotAccepted("already_done")
        if ticket.status != "waiting_for_approval":
            raise ApprovalNotAccepted("not_interrupted")
        binding = session.exec(
            select(RfpDepartmentAccount).where(RfpDepartmentAccount.user_id == user_id)
        ).first()
        if binding is None:
            raise ApprovalNotAccepted("not_department_owner", 403)
        try:
            run = _approval_run(ticket, metadata, rows)
            if resolution is not None and decision is not None:
                raise ApprovalNotAccepted("invalid_decision", 422)
            if resolution is not None:
                if department_id != "revenue":
                    raise ApprovalNotAccepted("not_capacity_arbiter", 403)
                run.resolve_capacity(actor_department_id=binding.department_id, resolution=resolution)
            elif decision is not None:
                run.decide(
                    department_id,
                    actor_department_id=binding.department_id,
                    submitted_by_user_id=user_id,
                    approver_name=binding.owner_name,
                    decision=decision,
                    note=note,
                )
            else:
                raise ApprovalNotAccepted("invalid_decision", 422)
        except ApprovalFlowError as exc:
            raise ApprovalNotAccepted(exc.code, _approval_status_code(exc.code)) from exc
        except ApprovalNotAccepted:
            raise
        _persist_approval(session, ticket, metadata, rows, run)


def get_final_document(session: Session, ticket_id: str) -> Any:
    from app.rfp_models import RfpFinalDocument
    from app.schemas.rfp import FinalDocumentPublic

    ticket = session.get(RfpTicket, ticket_id)
    if ticket is None:
        return None
    row = session.get(RfpFinalDocument, ticket_id)
    if row is None:
        return None
    return FinalDocumentPublic(
        ticket_id=row.ticket_id,
        sections=list(row.sections or []),
        currency=row.currency,
        generated_at=row.generated_at,
    )
