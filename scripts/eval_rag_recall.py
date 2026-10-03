"""Measure Recall@3 for the HealthCore knowledge retriever.

This script reports the embedding implementation that actually produced
the vectors. Do not treat a local FastEmbed run as a remote API model.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rag import embedding_backend, generation_backend, retrieve
from data.process.rag import setup
from shared.healthcore_rag.config import EVAL_QUERIES_PATH
from shared.healthcore_rag.qdrant import close_qdrant_client


def _is_hit(payloads: list[dict], expected_source: str, expected_chunk_index: int) -> bool:
    """A hit requires the expected source document and chunk_index in the top results."""
    for payload in payloads:
        if payload.get("source_document") != expected_source:
            continue
        if int(payload.get("chunk_index", -1)) == expected_chunk_index:
            return True
    return False


def main() -> int:
    backend = embedding_backend()
    summary = setup()
    questions = json.loads(EVAL_QUERIES_PATH.read_text(encoding="utf-8"))
    hits = 0
    rows: list[dict] = []
    for item in questions:
        retrieved = retrieve(item["question"], k=3, min_score=0.0)
        matched = _is_hit(
            retrieved,
            item["expected_source_document"],
            int(item["expected_chunk_index"]),
        )
        hits += int(matched)
        rows.append(
            {
                "id": item["id"],
                "hit": matched,
                "expected_source_document": item["expected_source_document"],
                "expected_chunk_index": item["expected_chunk_index"],
                "retrieved": [
                    {
                        "source_document": payload.get("source_document"),
                        "section": payload.get("section"),
                        "chunk_index": payload.get("chunk_index"),
                    }
                    for payload in retrieved
                ],
            }
        )

    total = len(questions)
    recall = hits / total if total else 0.0
    print(json.dumps(
        {
            "embedding_backend": backend,
            "generation_backend": generation_backend(),
            "validates_text_embedding_3_small": backend.startswith("api:text-embedding-3-small"),
            "collection": summary["collection"],
            "indexed_chunks": summary["chunk_count"],
            "chunks_per_document": summary["chunks_per_document"],
            "question_count": total,
            "hits": hits,
            "recall_at_3": recall,
            "meets_80_percent": recall >= 0.8,
            "questions": rows,
        },
        indent=2,
    ))
    close_qdrant_client()
    return 0 if recall >= 0.8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
