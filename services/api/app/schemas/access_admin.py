"""Admin role, department, and independent assignment contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.user import UserRole


class RoleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    rank: int = Field(ge=1, le=3)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    rank: int | None = Field(default=None, ge=1, le=3)


class RolePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    rank: int


class DepartmentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)


class DepartmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str


class UserAssignmentUpdate(BaseModel):
    """Independent role/department assignment. Omitted fields stay unchanged."""

    role_id: UserRole | None = None
    department_id: str | None = None


class UserAdminCreate(BaseModel):
    """Admin-only user create. Role and department are independent when supplied."""

    email: EmailStr
    password: str = Field(min_length=8)
    name: str | None = None
    phone: str | None = None
    address: str | None = None
    role_id: UserRole | None = None
    department_id: str | None = None
