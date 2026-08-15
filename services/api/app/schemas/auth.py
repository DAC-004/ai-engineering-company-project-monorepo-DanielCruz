"""Authentication request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr

from app.schemas.profile import ProfilePublic
from app.schemas.user import UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthMeResponse(BaseModel):
    email: EmailStr
    role: UserRole
    profile: ProfilePublic | None = None
