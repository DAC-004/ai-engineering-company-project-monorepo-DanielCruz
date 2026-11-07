"""Request and response models for Microsoft staff federated authentication."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


MICROSOFT_PROVIDER = "microsoft"
ALLOWED_PURPOSES = frozenset({"link", "login"})


class FederatedStartRequest(BaseModel):
    purpose: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)


class FederatedStartResponse(BaseModel):
    authorization_url: str
    state: str
    tx_binding: str


class FederatedCallbackRequest(BaseModel):
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)
    redirect_uri: str = Field(min_length=1)
    tx_binding: str = Field(min_length=1)


class FederatedLinkPublic(BaseModel):
    provider: str
    provider_user_id: str
    email_at_link_time: str | None = None
    linked_at: datetime | None = None
    provisioned_by_it: bool


class FederatedStatusResponse(BaseModel):
    provider: str = MICROSOFT_PROVIDER
    linked: bool
    link: FederatedLinkPublic | None = None
    has_password: bool
    can_unlink: bool
    unlink_blocked_reason: str | None = None
