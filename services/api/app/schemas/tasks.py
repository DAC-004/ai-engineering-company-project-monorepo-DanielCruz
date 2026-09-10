"""Task status response shapes for GET /tasks/{task_id}."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskEnqueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    result: Any | None = None
