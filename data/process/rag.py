"""HealthCore knowledge-base chunking and Qdrant indexing (`setup`)."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from qdrant_client.models import Distance, PointStruct, VectorParams

from data.pipelines.rag import embed
from shared.healthcore_rag.config import (
    COLLECTION_NAME,
    COMPANY,
    KNOWLEDGE_BASE_DIR,
    LANGUAGE,
    SOURCE_DOCUMENT_FILES,
    VECTOR_SIZE,
)
from shared.healthcore_rag.qdrant import get_qdrant_client

logger = logging.getLogger(__name__)

# Stable namespace so reruns of setup() write the same point IDs.
_POINT_NAMESPACE = uuid.UUID("8f3c2e1a-6b47-4d90-9c11-a1b2c3d4e5f6")


def _is_list_block(block: str) -> bool:
    first = block.lstrip()
    return first.startswith(("- ", "* ", "1.", "2.", "3.", "4."))


def _is_section_header_block(block: str) -> bool:
    first_line = block.split("\n", 1)[0].strip()
    if not first_line.endswith(":"):
        return False
    return not _is_list_block(first_line)


def _section_name(block: str, document_title: str) -> str:
    """Use the section title when present so retrieval stays traceable."""
    first_line = block.split("\n", 1)[0].strip()
    if first_line.endswith(":") and len(first_line) <= 120 and not _is_list_block(first_line):
        return first_line[:-1].strip()
    compact = " ".join(first_line.split())
    if len(compact) > 72:
        compact = compact[:72].rstrip() + "..."
    return compact or document_title


def chunk_markdown_document(text: str, source_document: str) -> list[dict[str, Any]]:
    """Split a HealthCore policy document into semantic chunks.

    Policy and procedure text is organized as a heading plus the complete
    rule group that follows it (bullets, numbered steps, or one paragraph).
    The splitter therefore:

    - keeps a header that ends with `:` together with its list
    - keeps an introductory sentence together with the numbered procedure
      it introduces
    - never splits a list, a condition, or an exception across chunks

    That is why the Medicare/Medicaid no-show exception stays in the same
    chunk as the private-pay cancellation fee, and why US and UK insurance
    rules stay in country-specific chunks.
    """
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    document_title = source_document
    body_lines: list[str] = []
    for line in normalized.split("\n"):
        if line.startswith("# ") and document_title == source_document:
            document_title = line[2:].strip()
            continue
        body_lines.append(line)

    raw_blocks: list[str] = []
    current: list[str] = []
    for line in body_lines:
        if line.strip() == "":
            if current:
                raw_blocks.append("\n".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        raw_blocks.append("\n".join(current).strip())

    # Attach a short intro that ends with ":" to the numbered/bullet list it
    # introduces, but do not swallow the next titled section.
    merged: list[str] = []
    index = 0
    while index < len(raw_blocks):
        block = raw_blocks[index]
        has_next = index + 1 < len(raw_blocks)
        next_block = raw_blocks[index + 1] if has_next else ""
        should_merge = (
            has_next
            and block.rstrip().endswith(":")
            and not _is_section_header_block(block)
            and _is_list_block(next_block)
            and not _is_section_header_block(next_block)
        )
        if should_merge:
            merged.append(f"{block}\n\n{next_block}")
            index += 2
            continue
        merged.append(block)
        index += 1

    chunks: list[dict[str, Any]] = []
    for chunk_index, block in enumerate(merged):
        chunks.append(
            {
                "company": COMPANY,
                "source_document": source_document,
                "section": _section_name(block, document_title),
                "language": LANGUAGE,
                "chunk_index": chunk_index,
                "text": block,
            }
        )
    return chunks


def load_source_documents(knowledge_dir: Path | None = None) -> list[tuple[str, str]]:
    """Read the four authorized HealthCore markdown files in stable order."""
    directory = knowledge_dir or KNOWLEDGE_BASE_DIR
    documents: list[tuple[str, str]] = []
    missing: list[str] = []
    for filename, source_document in SOURCE_DOCUMENT_FILES.items():
        path = directory / filename
        if not path.is_file():
            missing.append(filename)
            continue
        documents.append((source_document, path.read_text(encoding="utf-8")))
    if missing:
        raise FileNotFoundError(
            "Missing authorized HealthCore knowledge files: " + ", ".join(missing)
        )
    return documents


def build_chunks(knowledge_dir: Path | None = None) -> list[dict[str, Any]]:
    """Chunk every authorized source document and enforce the 3-chunk minimum."""
    chunks: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for source_document, text in load_source_documents(knowledge_dir):
        document_chunks = chunk_markdown_document(text, source_document)
        counts[source_document] = len(document_chunks)
        if len(document_chunks) < 3:
            raise ValueError(
                f"{source_document} produced {len(document_chunks)} chunks; "
                "each HealthCore source document must produce at least 3."
            )
        chunks.extend(document_chunks)
    logger.info("HealthCore chunk counts: %s", counts)
    return chunks


def deterministic_point_id(source_document: str, chunk_index: int, section: str) -> str:
    """UUID5 so a rerun upserts the same logical chunk instead of inserting a duplicate."""
    name = f"healthcore:{source_document}:{chunk_index}:{section}"
    return str(uuid.uuid5(_POINT_NAMESPACE, name))


def setup(knowledge_dir: Path | None = None) -> dict[str, Any]:
    """Create or recreate `healthcore_knowledge` and index every authorized chunk.

    Idempotency strategy: clear-and-reload plus deterministic UUID5 point IDs.
    `setup()` deletes the collection when it already exists, recreates it with
    the current vector size, and upserts one point per chunk. Rerunning during
    development therefore cannot accumulate duplicate points, and a chunking
    change cannot leave orphaned vectors from a previous split.
    """
    chunks = build_chunks(knowledge_dir)
    client = get_qdrant_client()

    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

    points: list[PointStruct] = []
    for chunk in chunks:
        # Include the section title in the indexed vector so policy headings
        # such as "Documents the patient should bring" remain searchable.
        # Payload `text` stays the chunk body used for prompt assembly.
        embed_input = f"{chunk['section']}\n\n{chunk['text']}"
        vector = embed(embed_input)
        if len(vector) != VECTOR_SIZE:
            raise ValueError(
                f"embed() returned {len(vector)} dimensions; "
                f"collection expects {VECTOR_SIZE}."
            )
        point_id = deterministic_point_id(
            chunk["source_document"],
            int(chunk["chunk_index"]),
            str(chunk["section"]),
        )
        points.append(PointStruct(id=point_id, vector=vector, payload=chunk))

    client.upsert(collection_name=COLLECTION_NAME, points=points)

    counts: dict[str, int] = {}
    for chunk in chunks:
        source_document = str(chunk["source_document"])
        counts[source_document] = counts.get(source_document, 0) + 1

    summary = {
        "collection": COLLECTION_NAME,
        "chunk_count": len(points),
        "chunks_per_document": counts,
    }
    logger.info("Indexed HealthCore knowledge: %s", summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(setup())
