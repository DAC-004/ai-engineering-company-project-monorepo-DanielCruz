"""HealthCore RAG configuration loaded from the environment.

Embedding and generation stay on separate model IDs. Secrets are never
hard-coded; only variable names and documented defaults live here.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_BASE_DIR = REPO_ROOT / "docs" / "company-knowledge-base"
EVAL_QUERIES_PATH = REPO_ROOT / "data" / "eval" / "test-queries.json"
DEFAULT_QDRANT_PATH = REPO_ROOT / "data" / "process" / "qdrant_storage"
DEFAULT_MODELS_DIR = REPO_ROOT / "data" / "process" / "models"

# Load repo-root and API env files if present. Existing process env wins.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "services" / "api" / ".env")

COMPANY = "healthcore"
COLLECTION_NAME = "healthcore_knowledge"
LANGUAGE = "en"

# Filename -> CONTEXT payload enum value.
SOURCE_DOCUMENT_FILES: dict[str, str] = {
    "healthcore-insurance-coverage.en.md": "insurance-coverage",
    "healthcore-appointment-policy.en.md": "appointment-policy",
    "healthcore-referral-process.en.md": "referral-process",
    "healthcore-new-patient-checklist.en.md": "new-patient-checklist",
}


def _env(*names: str, default: str = "") -> str:
    """Return the first non-empty environment value, then default."""
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return default


# Dedicated local models. These IDs are the executed implementations when no
# remote key is configured. They are not 4Geeks-provided catalog names; the
# assignment prefers course models where applicable but does not name one.
LOCAL_EMBEDDING_MODEL_ID = "BAAI/bge-small-en-v1.5"
LOCAL_GENERATION_MODEL_ID = "Qwen2.5-3B-Instruct"
LOCAL_GENERATION_GGUF_REPO = "Qwen/Qwen2.5-3B-Instruct-GGUF"
LOCAL_GENERATION_GGUF_FILENAME = "qwen2.5-3b-instruct-q4_k_m.gguf"

EMBEDDING_MODEL_ID = _env("EMBEDDING_MODEL", default=LOCAL_EMBEDDING_MODEL_ID)
GENERATION_MODEL_ID = _env(
    "GENERATION_MODEL",
    "LLM_MODEL",
    default=LOCAL_GENERATION_MODEL_ID,
)

# FastEmbed BAAI/bge-small-en-v1.5 emits 384-d vectors. Recreate the
# collection if this width changes.
VECTOR_SIZE = int(_env("EMBEDDING_VECTOR_SIZE", default="384"))
QDRANT_DISTANCE = "Cosine"

# Production floor for bge-small-en-v1.5 cosine on this 15-chunk corpus.
# Retuned from live retrieval scores; see docs/rag/rag-design.md.
DEFAULT_MIN_SCORE = float(_env("RAG_MIN_SCORE", default="0.45"))
DEFAULT_K = 3

EMBEDDING_API_URL = _env("EMBEDDING_API_URL", "LLM_API_URL").rstrip("/")
GENERATION_API_URL = _env("GENERATION_API_URL", "LLM_API_URL").rstrip("/")

EMBEDDING_API_KEY = _env("EMBEDDING_API_KEY", "LLM_API_KEY")
GENERATION_API_KEY = _env("GENERATION_API_KEY", "LLM_API_KEY")

QDRANT_URL = _env("QDRANT_URL")
QDRANT_API_KEY = _env("QDRANT_API_KEY")
QDRANT_PATH = _env("QDRANT_PATH", default=str(DEFAULT_QDRANT_PATH))
MODELS_DIR = Path(_env("RAG_MODELS_DIR", default=str(DEFAULT_MODELS_DIR)))


def embedding_and_generation_models_differ() -> bool:
    return EMBEDDING_MODEL_ID != GENERATION_MODEL_ID
