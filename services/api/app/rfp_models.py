"""SQLModel tables for RFP intake. TinyDB is not the source of truth for these rows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class RfpTicket(SQLModel, table=True):
    """One uploaded RFP. The same id continues into later parts."""

    __tablename__ = "rfp_ticket"

    ticket_id: str = Field(primary_key=True, max_length=36)
    status: str = Field(max_length=32, index=True)
    raw_pdf_path: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    processing_error_code: str | None = Field(default=None, max_length=64)
    processing_failed: bool = Field(default=False)
    phi_detected: bool = Field(default=False)
    compliance_review_required: bool = Field(default=False)
    part2_handoff: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    part3_handoff: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class RfpMetadata(SQLModel, table=True):
    """Company-context metadata and readability metrics. No patient columns."""

    __tablename__ = "rfp_metadata"

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_ticket.ticket_id", unique=True, index=True, max_length=36)
    client_name: str | None = Field(default=None, max_length=200)
    client_country: str | None = Field(default=None, max_length=2)
    program_type: str | None = Field(default=None, max_length=200)
    covered_population: str | None = Field(default=None, max_length=200)
    deadline: str | None = Field(default=None, max_length=200)
    budget_range: str | None = Field(default=None, max_length=200)
    departments_needed: list[str] | None = Field(default=None, sa_column=Column(JSON))
    flesch_kincaid_grade: float | None = Field(default=None)
    gunning_fog: float | None = Field(default=None)


class DepartmentSection(SQLModel, table=True):
    """Per-department key aspects, and later the Part 2 draft and evaluation."""

    __tablename__ = "rfp_department_section"

    id: int | None = Field(default=None, primary_key=True)
    ticket_id: str = Field(foreign_key="rfp_ticket.ticket_id", index=True, max_length=36)
    department_id: str = Field(max_length=32, index=True)
    key_aspects: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    draft_content: str | None = Field(default=None)
    evaluation_results: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    needs_human_review: bool = Field(default=False)
