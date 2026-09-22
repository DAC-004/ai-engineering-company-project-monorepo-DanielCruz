"""HealthCore knowledge query endpoint. Delegates to the pipeline `query()`."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.knowledge import KnowledgeQueryRequest, KnowledgeQueryResponse
from data.pipelines.rag import query as pipeline_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/query", response_model=KnowledgeQueryResponse)
def knowledge_query(body: KnowledgeQueryRequest) -> KnowledgeQueryResponse:
    """Return only the generated answer string. No retrieval payloads leave this router."""
    try:
        answer = pipeline_query(body.question)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        logger.exception("HealthCore knowledge query failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The knowledge assistant could not generate an answer right now.",
        ) from None
    return KnowledgeQueryResponse(answer=answer)
