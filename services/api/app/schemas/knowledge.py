"""Public request and response contract for POST /knowledge/query."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)


class KnowledgeQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
