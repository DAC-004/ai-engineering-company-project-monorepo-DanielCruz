"""Response shapes for RFP intake. These are not the SQLModel tables."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class RfpTicketCreated(BaseModel):
    ticket_id: str
    status: str


class DepartmentSectionPublic(BaseModel):
    department_id: str
    department_name: str | None = None
    contact_name: str | None = None
    key_aspects: dict[str, Any]
    draft_content: str | None = None
    evaluation_results: dict[str, Any] | None = None
    needs_human_review: bool = False
    approval_status: str | None = None
    approver: str | None = None
    approved_at: datetime | None = None
    approved_content_sha256: str | None = None
    submitted_by_user_id: str | None = None
    approval_revision_count: int = 0
    iteration_limit_reached: bool = False


class RfpMetadataPublic(BaseModel):
    client_name: str | None
    client_country: str | None
    program_type: str | None
    covered_population: str | None
    deadline: str | None
    budget_range: str | None
    departments_needed: list[str]
    flesch_kincaid_grade: float | None
    gunning_fog: float | None


class RfpTicketPublic(BaseModel):
    ticket_id: str
    status: str
    raw_pdf_path: str | None
    created_at: datetime
    updated_at: datetime
    processing_failed: bool
    processing_error_code: str | None
    stalled: bool
    phi_detected: bool
    compliance_review_required: bool
    metadata: RfpMetadataPublic | None
    sections: list[DepartmentSectionPublic]
    synthesizer_summary: str | None
    part2_handoff: dict[str, Any] | None
    part3_handoff: dict[str, Any] | None = None
    node_trace: list[dict[str, Any]] | None = None
    arbitration_state: dict[str, Any] | None = None


class DepartmentDecision(BaseModel):
    decision: Literal["approve", "reject", "request_changes"] | None = None
    note: str | None = None
    resolution: Literal["reduce_covered_population", "add_sites"] | None = None


class FinalDocumentPublic(BaseModel):
    ticket_id: str
    sections: list[dict[str, Any]]
    currency: str | None
    generated_at: datetime
