"""Public request and response contract for POST /agent/query."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AgentQueryRequest(BaseModel):
    """Accept an empty question so the graph can route it.

    ``min_length`` is intentionally omitted. Whitespace is also accepted here
    and rejected by the graph before retrieval. The field itself is required.
    """

    model_config = ConfigDict(extra="forbid")

    question: str


class AgentQueryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    trace_id: str
