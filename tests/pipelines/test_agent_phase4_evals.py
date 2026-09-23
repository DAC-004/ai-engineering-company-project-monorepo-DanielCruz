"""Executing Part 2 routing evals.

Run the default command from ``services/api`` with ``PART2_LIVE_RAG_EVAL``
unset. A fresh clone does not contain the ignored Qdrant index or GGUF.

    uv run pytest --rootdir . ../../tests/pipelines/test_agent_phase4_evals.py -q -p no:cacheprovider --tb=short

That command executes three tests and skips the live retrieval test before
any RAG call:

- ``test_ticket_eval_reads_the_real_service_twice`` reads the integrated
  incident service. It is not patched.
- ``test_knowledge_routing_eval_patches_retrieval_and_generation`` runs the
  compiled graph. Only ``retrieve()`` and ``generate_answer()`` are patched,
  using text from the committed referral-policy document.
- ``test_failure_eval_finishes_without_a_fabricated_status`` reads the
  incident service for a missing id. It is not patched.

Opt-in live retrieval, in PowerShell, still from ``services/api``:

    $env:PART2_LIVE_RAG_EVAL = "1"
    uv run pytest --rootdir . ../../tests/pipelines/test_agent_phase4_evals.py -q -p no:cacheprovider --tb=short -k test_knowledge_eval_uses_real_retrieval_and_local_generation

``test_knowledge_eval_uses_real_retrieval_and_local_generation`` then checks
that the local index and GGUF exist, and only after that calls real
``retrieve()`` and local generation. It does not download a model.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_SHARED = REPO_ROOT / "packages" / "shared"
API_ROOT = REPO_ROOT / "services" / "api"
for _import_path in (API_ROOT, REPO_ROOT, PACKAGES_SHARED):
    if str(_import_path) not in sys.path:
        sys.path.insert(0, str(_import_path))

from app.agent.graph import run_support_agent
from app.agent.routing import HONEST_STATUS_SENTENCE
from app.agent.tracing import load_trace

REFERRAL_DOCUMENT = (
    REPO_ROOT / "docs" / "company-knowledge-base" / "healthcore-referral-process.en.md"
)
TRACE_DIR = REPO_ROOT / "data" / "process" / "agent_traces"
CHECKPOINT_PATH = REPO_ROOT / "data" / "process" / "agent_checkpoints" / "phase4_evals.sqlite"
LIVE_RAG_EVAL_ENV = "PART2_LIVE_RAG_EVAL"
POLICY_SENTENCE = (
    "Target completed-referral time: 11 days from creation to confirmed appointment"
)
STATUS_WORDS = ("open", "in_progress", "resolved", "discarded")
_ANSWER_FIELDS = re.compile(
    r"Incident (?P<id>[0-9a-fA-F-]{36}) status is (?P<status>[A-Za-z0-9_]+)\. "
    r"Category: (?P<category>[A-Za-z0-9_]+)\. Origin: (?P<origin>[A-Za-z0-9_]+)\."
)


def _policy_sentence() -> str:
    """Load the referral timing sentence from the policy file.

    The file wraps the sentence and continues with a parenthetical. The
    approved fact is the wording through ``appointment``, read from the file
    rather than from a graph trace.
    """
    collapsed = " ".join(REFERRAL_DOCUMENT.read_text(encoding="utf-8").split())
    if POLICY_SENTENCE not in collapsed:
        raise AssertionError("The referral policy file does not contain the 11-day sentence.")
    if "11 days" not in POLICY_SENTENCE:
        raise AssertionError("The policy sentence does not contain the 11-day fact.")
    return POLICY_SENTENCE


def _live_rag_requested() -> bool:
    return os.environ.get(LIVE_RAG_EVAL_ENV, "").strip().lower() in {"1", "true", "yes"}


def _require_local_rag_assets() -> None:
    """Fail before the graph runs when the ignored local assets are absent.

    ``generate_answer()`` downloads the GGUF when that file is missing.
    This check runs first so the opt-in eval never reaches that download
    and never replaces the live path with a mock.
    """
    from shared.healthcore_rag.config import (
        COLLECTION_NAME,
        GENERATION_API_KEY,
        LOCAL_GENERATION_GGUF_FILENAME,
        MODELS_DIR,
        QDRANT_PATH,
        QDRANT_URL,
    )

    if QDRANT_URL:
        pytest.fail(
            "Unset QDRANT_URL before the live RAG eval so retrieval uses the "
            "local embedded index."
        )
    if GENERATION_API_KEY:
        pytest.fail(
            "Unset GENERATION_API_KEY before the live RAG eval so generation "
            "uses the local GGUF instead of a remote model."
        )

    index_file = Path(QDRANT_PATH) / "collection" / COLLECTION_NAME / "storage.sqlite"
    model_file = MODELS_DIR / LOCAL_GENERATION_GGUF_FILENAME
    missing: list[str] = []
    if not index_file.is_file():
        missing.append(f"Qdrant collection file {index_file}")
    if not model_file.is_file() or model_file.stat().st_size <= 0:
        missing.append(f"GGUF file {model_file}")
    if missing:
        pytest.fail(
            f"{LIVE_RAG_EVAL_ENV} is set, but the local RAG assets are absent: "
            + "; ".join(missing)
            + ". Place those ignored files locally. This test does not download "
            "a model and does not substitute mocked retrieval."
        )


def _run(question: str, *, authenticated: bool) -> tuple[object, dict]:
    outcome = run_support_agent(
        question,
        caller_is_authenticated=authenticated,
        checkpoint_path=CHECKPOINT_PATH,
        trace_dir=TRACE_DIR,
    )
    return outcome, load_trace(outcome.trace_id, TRACE_DIR)


def _answer_fields(answer: str) -> dict[str, str]:
    match = _ANSWER_FIELDS.search(answer)
    if match is None:
        raise AssertionError(f"Answer did not report id, status, category, and origin: {answer}")
    return match.groupdict()


def _assert_matches_read(answer: str, row: object) -> None:
    reported = _answer_fields(answer)
    assert reported["id"] == row.id
    assert reported["status"] == row.status
    assert reported["category"] == row.category
    assert reported["origin"] == row.origin


def test_ticket_eval_reads_the_real_service_twice(tmp_path: Path, monkeypatch) -> None:
    from app.core.config import get_settings
    from app.db.database import reset_engine_for_tests
    from app.db.tinydb import reset_db_for_tests
    from app.schemas.incident import IncidentCreate
    from app.services import incident_service

    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "phase4-incidents.json"))
    monkeypatch.setenv("SECRET_KEY", "isolated-phase4-secret-key-32b")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'phase4-inventory.db').as_posix()}")
    get_settings.cache_clear()
    reset_db_for_tests()
    reset_engine_for_tests()
    try:
        created = incident_service.create_incident(
            IncidentCreate(
                title="Synthetic pump alarm",
                description="Phase 4 synthetic ticket body",
                category="clinical_equipment",
                status="open",
                origin="branch",
                branch="central",
            )
        )
        question = f"What is the status of incident {created.id}?"
        assert "knowledge base" not in question.lower()
        assert "use the tool" not in question.lower()

        first_outcome, first_trace = _run(question, authenticated=True)
        first_read = incident_service.get_incident(created.id)
        assert first_trace["sources"] == ["ticket_tool"]
        assert "lookup_ticket" in first_trace["node_order"]
        assert "retrieve_context" not in first_trace["node_order"]
        _assert_matches_read(str(first_outcome.answer), first_read)
        _assert_no_ticket_body(first_trace, created.title, created.description)

        incident_service.update_incident_status(created.id, "in_progress")
        second_outcome, second_trace = _run(question, authenticated=True)
        second_read = incident_service.get_incident(created.id)
        assert second_read.status == "in_progress"
        assert second_trace["sources"] == ["ticket_tool"]
        assert "retrieve_context" not in second_trace["node_order"]
        _assert_matches_read(str(second_outcome.answer), second_read)
        assert second_read.status in str(second_outcome.answer)
        assert first_read.status not in _answer_fields(str(second_outcome.answer))["status"]
        _assert_no_ticket_body(second_trace, created.title, created.description)
    finally:
        reset_db_for_tests()
        reset_engine_for_tests()
        get_settings.cache_clear()


def test_knowledge_routing_eval_patches_retrieval_and_generation(monkeypatch) -> None:
    """Asset-free knowledge routing. Retrieval and generation are patched.

    The compiled graph still chooses the nodes and writes the trace.
    ``retrieve()`` returns a chunk copied from the referral-policy file.
    ``generate_answer()`` copies that chunk into the answer, so a bypassed
    generator or a missing context fails the assertion.
    """
    sentence = _policy_sentence()
    calls = {"retrieve": 0, "generate": 0}
    service_calls = {"n": 0}

    def fail_incident_read(*_args: object, **_kwargs: object) -> None:
        service_calls["n"] += 1
        raise AssertionError("patched knowledge eval called an incident read")

    def patched_retrieve(_query: str, **_kwargs: object) -> list[dict[str, object]]:
        calls["retrieve"] += 1
        return [
            {
                "company": "healthcore",
                "source_document": "referral-process",
                "section": "Target completed-referral time",
                "language": "en",
                "chunk_index": 1,
                "text": sentence,
            }
        ]

    def patched_generate(_question: str, context: list[object]) -> str:
        """Return the supplied chunk text, or a marker when it is missing."""
        calls["generate"] += 1
        retrieved_text = " ".join(
            str(chunk.get("text", ""))
            for chunk in context
            if isinstance(chunk, dict)
        )
        if sentence not in retrieved_text:
            return "UNGROUNDED"
        return f"The retrieved referral policy says: {retrieved_text}"

    monkeypatch.setattr("data.pipelines.rag.retrieve", patched_retrieve)
    monkeypatch.setattr("data.pipelines.rag.generate_answer", patched_generate)
    monkeypatch.setattr("app.services.incident_service.get_incident", fail_incident_read)
    monkeypatch.setattr("app.services.incident_service.list_incidents", fail_incident_read)

    question = "How long does an internal referral take?"
    outcome, stored = _run(question, authenticated=False)
    assert calls["retrieve"] == 1
    assert calls["generate"] == 1
    assert service_calls["n"] == 0
    assert stored["sources"] == ["rag"]
    assert "lookup_ticket" not in stored["node_order"]
    assert stored["node_order"].index("retrieve_context") < stored["node_order"].index(
        "generate_from_context"
    )
    retrieved_chunks = [
        chunk
        for chunk in stored["context"]
        if isinstance(chunk, dict) and chunk.get("source_document") == "referral-process"
    ]
    assert retrieved_chunks
    assert sentence in str(retrieved_chunks[0].get("text", ""))
    assert sentence in str(outcome.answer)
    assert "11 days" in str(outcome.answer)
    generated = next(
        node for node in stored["nodes"] if node["node"] == "generate_from_context"
    )
    assert sentence in str(generated["output"].get("answer", ""))
    for word in STATUS_WORDS:
        assert word not in str(outcome.answer)
    assert stored["error"] == ""


def test_knowledge_eval_uses_real_retrieval_and_local_generation() -> None:
    """Live retrieval and local GGUF generation. Opt in with PART2_LIVE_RAG_EVAL.

    Without the variable this returns before any RAG call. With the variable
    set, missing local assets fail here instead of downloading a model.
    """
    if not _live_rag_requested():
        pytest.skip(
            f"Set {LIVE_RAG_EVAL_ENV}=1 to run real Qdrant retrieval and local "
            "GGUF generation. The default Part 2 eval skips this test and does "
            "not download a model."
        )
    _require_local_rag_assets()
    sentence = _policy_sentence()
    phrase = "11 days"
    assert phrase in sentence

    question = "How long does an internal referral take?"
    outcome, stored = _run(question, authenticated=False)
    assert stored["sources"] == ["rag"]
    assert "retrieve_context" in stored["node_order"]
    assert "generate_from_context" in stored["node_order"]
    assert "lookup_ticket" not in stored["node_order"]
    assert stored["node_order"].index("retrieve_context") < stored["node_order"].index(
        "generate_from_context"
    )
    referral_chunks = [
        chunk
        for chunk in stored["context"]
        if isinstance(chunk, dict) and chunk.get("source_document") == "referral-process"
    ]
    assert referral_chunks
    retrieved = " ".join(str(chunk.get("text", "")) for chunk in referral_chunks)
    assert phrase in retrieved
    assert phrase in str(outcome.answer)
    for word in STATUS_WORDS:
        assert word not in str(outcome.answer)
    assert stored["error"] == ""


def test_failure_eval_finishes_without_a_fabricated_status(tmp_path: Path, monkeypatch) -> None:
    from app.core.config import get_settings
    from app.db.database import reset_engine_for_tests
    from app.db.tinydb import reset_db_for_tests

    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "phase4-missing.json"))
    monkeypatch.setenv("SECRET_KEY", "isolated-phase4-secret-key-32b")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'phase4-missing.db').as_posix()}")
    get_settings.cache_clear()
    reset_db_for_tests()
    reset_engine_for_tests()
    try:
        question = "What is the status of incident 55555555-5555-4555-8555-555555555555?"
        outcome, stored = _run(question, authenticated=True)
        assert outcome.error == ""
        assert stored["answer"] == HONEST_STATUS_SENTENCE
        assert stored["lookup_failure"] == "missing"
        assert "lookup_ticket" in stored["node_order"]
        assert (TRACE_DIR / f"{outcome.trace_id}.json").is_file()
        for word in STATUS_WORDS:
            assert word not in stored["answer"]
    finally:
        reset_db_for_tests()
        reset_engine_for_tests()
        get_settings.cache_clear()


def _assert_no_ticket_body(stored: dict, title: str, description: str) -> None:
    trace_text = str(stored)
    assert title not in trace_text
    assert description not in trace_text
    assert stored["ticket_id"]
    assert stored["ticket_status"] in STATUS_WORDS
    assert stored["sources"] == ["ticket_tool"]
    assert "title" not in stored
    assert "description" not in stored
