"""Pydantic schemas for Profile (display/contact data linked 1:1 to User via user_id)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProfileCreate(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class ProfileUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class ProfilePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class ProfileUpsert(BaseModel):
    """Internal helper for registration-time profile creation."""

    name: str = Field(default="")
    phone: str = Field(default="")
    address: str = Field(default="")
