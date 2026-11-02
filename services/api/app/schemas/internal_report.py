"""Internal-reports collection from the specialized roles briefing."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InternalReportCreate(BaseModel):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    department_id: str | None = None


class InternalReportUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    body: str | None = Field(default=None, min_length=1)


class InternalReportPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    department_id: str
    title: str
    body: str
    created_by: str
    created_at: datetime
