"""Pydantic schemas for Centralized Incident Manager records."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IncidentCreate(BaseModel):
    """Operator-supplied create payload. Generated fields are ignored if sent."""

    model_config = ConfigDict(extra="ignore")

    title: str
    description: str
    category: str
    status: str = "open"
    origin: str
    branch: str


class IncidentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str


class IncidentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    category: str
    status: str
    origin: str
    branch: str
    created_at: datetime
    updated_at: datetime


class IncidentInDB(IncidentPublic):
    pass


class IncidentSummary(BaseModel):
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_origin: dict[str, int] = Field(default_factory=dict)
    by_branch: dict[str, int] = Field(default_factory=dict)
