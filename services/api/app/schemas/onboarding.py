"""Public onboarding request and response models. No sensitive fields."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OnboardingStartRequest(BaseModel):
    hire_user_id: str
    display_name: str
    role_key: str
    department_id: str
    office: str
    framework: str
    manager_user_id: str
    claire_user_id: str
    diane_user_id: str
    start_date: str
    onboarding_id: str | None = None


class PeopleReceiptRequest(BaseModel):
    documents_received: bool
    background_check_completed: bool
    decision_nonce: str


class CheckSubmitRequest(BaseModel):
    answers: list[int]
    decision_nonce: str


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    comment: str = ""
    decision_nonce: str


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class AccessRequestBody(BaseModel):
    system_id: str


class OnboardingPublic(BaseModel):
    onboarding_id: str
    current_stage: int
    stage_name: str
    status: str
    pending_kind: str
    blocked: bool
    last_action: str
    last_rejection_comment: str = ""
    office: str | None = None
    display_name: str | None = None
    department_id: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
