"""Graph-backed support query. This module does not retrieve or generate.

Question classification chooses whether a missing bearer is allowed. It is
not the authorization boundary for the incident read. The graph lookup
checks ``caller_is_authenticated`` again before any incident-service call.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.agent.graph import run_support_agent
from app.agent.routing import classify_question
from app.core.deps import CREDENTIALS_EXCEPTION, get_current_user
from app.schemas.agent import AgentQueryRequest, AgentQueryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

AGENT_FAILURE_DETAIL = "The knowledge assistant could not generate an answer right now."
optional_bearer = HTTPBearer(auto_error=False)


@router.post("/query", response_model=AgentQueryResponse)
def agent_query(
    body: AgentQueryRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
) -> AgentQueryResponse:
    """Invoke the compiled graph and translate its result into HTTP.

    A knowledge-only or empty question with no bearer stays on the public
    RAG path. A ticket or combined question with no valid bearer returns
    401 before ``run_support_agent``. A present bearer is accepted only by
    ``get_current_user``. The token is not stored on the graph state.
    """
    route_kind = classify_question(body.question)
    caller_is_authenticated = False
    if credentials is not None:
        get_current_user(credentials.credentials)
        caller_is_authenticated = True
    elif route_kind in {"ticket", "both"}:
        raise CREDENTIALS_EXCEPTION
    try:
        outcome = run_support_agent(
            body.question,
            caller_is_authenticated=caller_is_authenticated,
        )
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
