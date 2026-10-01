"""Persist intake results and run the pipeline off the request thread."""

from __future__ import annotations

import logging
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
from data.pipelines.rfp_intake.generation import ChatComplete
from data.pipelines.rfp_intake.phi import screen_structure
from data.pipelines.rfp_intake.runner import IntakeRun, process_pdf

logger = logging.getLogger("healthcore.rfp_intake")

STALE_AFTER = timedelta(minutes=15)
RUNNING_TICKETS: set[str] = set()
# Test hooks. Production leaves both unset, so the pipeline uses local llama.cpp
# and data/raw/rfp_intake. A background task can read these because they are
# process state, not a request-scoped context variable.
complete_override_fn: ChatComplete | None = None
storage_override: Path | None = None


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
        )
        for section in sections
    ]
    payload: dict[str, Any] = {
        "summary": summary,
        "metadata": metadata_public.model_dump() if metadata_public else None,
        "sections": [item.model_dump() for item in section_public],
        "handoff": ticket.part2_handoff,
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
