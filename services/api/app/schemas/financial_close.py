from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FinancialCloseApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str = Field(min_length=32, max_length=36, pattern=r"^[0-9a-fA-F-]{32,36}$")
    version: int = Field(ge=1)
    content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    approval_nonce: str = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")
    decision: Literal["approve", "reject"]
    comments: str | None = Field(default=None, max_length=4000)


class FinancialCloseJobQueued(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: Literal["queued"]
    task_id: str | None = None
