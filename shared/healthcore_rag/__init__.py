"""HealthCore RAG shared constants and Qdrant helpers."""

from shared.healthcore_rag.config import (
    COLLECTION_NAME,
    COMPANY,
    DEFAULT_K,
    DEFAULT_MIN_SCORE,
    EMBEDDING_MODEL_ID,
    GENERATION_MODEL_ID,
    KNOWLEDGE_BASE_DIR,
    LANGUAGE,
    SOURCE_DOCUMENT_FILES,
    VECTOR_SIZE,
)
from shared.healthcore_rag.qdrant import close_qdrant_client, get_qdrant_client

__all__ = [
    "COLLECTION_NAME",
    "COMPANY",
    "DEFAULT_K",
    "DEFAULT_MIN_SCORE",
    "EMBEDDING_MODEL_ID",
    "GENERATION_MODEL_ID",
    "KNOWLEDGE_BASE_DIR",
    "LANGUAGE",
    "SOURCE_DOCUMENT_FILES",
    "VECTOR_SIZE",
    "close_qdrant_client",
    "get_qdrant_client",
]
