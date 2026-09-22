"""Graph-backed support query. This module does not retrieve or generate."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.agent.graph import run_support_agent
from app.schemas.agent import AgentQueryRequest, AgentQueryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

AGENT_FAILURE_DETAIL = "The knowledge assistant could not generate an answer right now."


@router.post("/query", response_model=AgentQueryResponse)
def agent_query(body: AgentQueryRequest) -> AgentQueryResponse:
    """Invoke the compiled graph and translate its result into HTTP."""
    try:
        outcome = run_support_agent(body.question)
    except Exception:
        logger.exception("HealthCore support agent query failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=AGENT_FAILURE_DETAIL,
        ) from None
    if outcome.error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=outcome.error,
        )
    return AgentQueryResponse(answer=outcome.answer, trace_id=outcome.trace_id)
