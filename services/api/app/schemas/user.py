"""Pydantic schemas for User account entities (credentials only — no profile fields)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserRole(str, Enum):
    employee = "employee"
    supervisor = "supervisor"
    admin = "admin"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    # Optional initial profile fields accepted at registration only.
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    is_active: bool | None = None
    role: UserRole | None = None
    department_id: str | None = None


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    is_active: bool
    role: UserRole
    role_id: UserRole | None = None
    department_id: str | None = None
    created_at: datetime

    @model_validator(mode="after")
    def sync_role_id(self) -> UserPublic:
        if self.role_id is None:
            self.role_id = self.role
        return self


class UserInDB(UserPublic):
    hashed_password: str
