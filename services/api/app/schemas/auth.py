"""Authentication request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.schemas.profile import ProfilePublic
from app.schemas.user import UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthMeResponse(BaseModel):
    email: EmailStr
    role: UserRole
    profile: ProfilePublic | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class PasswordActionResponse(BaseModel):
    detail: str
