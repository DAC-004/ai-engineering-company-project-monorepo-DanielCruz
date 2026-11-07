"""Public contracts for the Task 4 supervisor. TinyDB supplier floats are not reused."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RequestKind = Literal[
    "question",
    "evaluate_increase",
    "impact",
    "compare",
    "brief",
    "draft_communication",
    "missing_agreements",
]


class SupplierContractsAsk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: RequestKind = "question"
    question: str = Field(min_length=1)
    supplier_id: str | None = None


class SupplierContractsApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str = Field(min_length=1)
    version: int
    content_sha256: str = Field(min_length=1)
    approval_nonce: str = Field(min_length=1)


class SupplierContractsDpaProceed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: str = Field(min_length=1)


class SupplierContractsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any]
