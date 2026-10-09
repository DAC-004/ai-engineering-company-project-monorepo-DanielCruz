"""HealthCore knowledge query endpoint. Delegates to the pipeline `query()`."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.core.safe_errors import log_failure
from app.schemas.knowledge import KnowledgeQueryRequest, KnowledgeQueryResponse
from data.pipelines.rag import query as pipeline_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

KNOWLEDGE_BAD_REQUEST_DETAIL = "The knowledge request could not be processed."
KNOWLEDGE_FAILURE_DETAIL = "The knowledge assistant could not generate an answer right now."


@router.post("/query", response_model=KnowledgeQueryResponse)
def knowledge_query(body: KnowledgeQueryRequest) -> KnowledgeQueryResponse:
    """Return only the generated answer string. No retrieval payloads leave this router."""
    try:
        answer = pipeline_query(body.question)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=KNOWLEDGE_BAD_REQUEST_DETAIL,
        ) from None
    except Exception:
        log_failure(logger, "HealthCore knowledge query failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=KNOWLEDGE_FAILURE_DETAIL,
        ) from None
    return KnowledgeQueryResponse(answer=answer)
