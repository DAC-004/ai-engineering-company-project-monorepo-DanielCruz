"""Typed specialist I/O. Figures travel as Decimal or Decimal strings, never float."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

Confidence = Literal["high", "uncertain"]
RequestKind = Literal[
    "question",
    "evaluate_increase",
    "impact",
    "compare",
    "brief",
    "draft_communication",
    "missing_agreements",
    "tick_alerts",
]


@dataclass(frozen=True)
class PriceRow:
    row_id: str
    supplier_id: str
    product: str
    unit: str
    currency: str
    month: str
    unit_price: Decimal
    monthly_volume: Decimal
    source_path: str


@dataclass(frozen=True)
class PricingRequest:
    supplier_id: str
    calculation: Literal["history", "increase", "impact", "compare"]
    product: str | None = None
    month_from: str | None = None
    month_to: str | None = None


@dataclass(frozen=True)
class AlternativeQuote:
    supplier_id: str
    display_name: str
    unit_price: Decimal
    currency: str
    quote_only: bool
    same_country: bool
    same_category: bool
    hypothetical_annual_difference: Decimal | None
    source_row_ids: tuple[str, ...]
    availability_assumed: bool = False


@dataclass(frozen=True)
class PricingResult:
    supplier_id: str
    product: str
    unit: str
    currency: str
    previous_price: Decimal | None
    current_price: Decimal | None
    change_ratio: Decimal | None
    above_threshold: bool
    annual_incremental: Decimal | None
    annual_incremental_usd: Decimal | None
    formula: str
    source_row_ids: tuple[str, ...]
    alternatives: tuple[AlternativeQuote, ...]
    quote_only: bool
    missing: tuple[str, ...]
    observation_from: str | None
    observation_to: str | None
    actor_id: str


@dataclass(frozen=True)
class TermCitation:
    field: str
    value: str
    clause: str
    page: int
    pdf_sha256: str
    confidence: Confidence
    status: Literal["present", "missing", "uncertain"]


@dataclass(frozen=True)
class ContractsRequest:
    supplier_id: str
    question: str
    contract_id: str | None = None


@dataclass(frozen=True)
class ContractsResult:
    supplier_id: str
    contract_id: str | None
    missing_contract: bool
    terms: tuple[TermCitation, ...]
    increase_allowed: bool | None
    cap_ratio: Decimal | None
    cap_price: Decimal | None
    missing_dpa: bool
    processes_patient_data: bool
    dpa_status: str
    exit_penalty_uncertain: bool
    expiry_offset_days: int | None
    notice_days: int | None
    pdf_sha256: str | None
    actor_id: str
    estimated_annual_value: Decimal | None = None
    estimated_annual_currency: str | None = None
    estimated_annual_uncertain: bool = False


@dataclass(frozen=True)
class SupervisorRequest:
    kind: RequestKind
    question: str
    supplier_id: str | None = None
    actor_user_id: str = ""
    actor_role: str = ""
    actor_department_id: str = ""
    actor_email: str = ""


@dataclass(frozen=True)
class SupervisorResponse:
    answer: str
    blocked: bool
    block_reason: str | None
    pricing: PricingResult | None
    contracts: ContractsResult | None
    citations: tuple[str, ...]
    consultation_count: int
    required_approvers: tuple[str, ...]
    alerts: tuple[dict, ...]
    actor_id: str
    draft: dict | None = None


@dataclass
class ApprovalState:
    draft_id: str
    supplier_id: str
    kind: Literal["brief", "draft_communication"]
    version: int
    content_sha256: str
    approval_nonce: str
    required: list[str]
    granted: list[str] = field(default_factory=list)
    state: Literal["pending", "approved", "rejected"] = "pending"
    claire_dpa_proceed: bool = False
    sent: bool = False
