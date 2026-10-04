"""Live local-GGUF evidence for gated generation.

Skipped unless PART2_LIVE_GATED_GENERATION=1. A fake model cannot satisfy this
file. The gate does not provide universal PHI detection.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from app.agent.nodes import generate_from_context
from data.pipelines.rag import (
    LocalGenerationWatch,
    bind_local_generation_watch,
    reset_local_generation_watch,
)
from shared.healthcore_rag.config import GENERATION_API_KEY, LOCAL_GENERATION_GGUF_FILENAME, MODELS_DIR

LIVE_ENV = "PART2_LIVE_GATED_GENERATION"
_COMPLIANCE_CONTEXT = (
    "HIPAA permits covered entities to use or disclose protected health "
    "information for treatment, payment, and healthcare operations, subject "
    "to applicable conditions and safeguards. The minimum necessary standard "
    "generally requires reasonable efforts to limit information used, "
    "requested, or disclosed to what is needed for the purpose. Source: HHS, "
    "Summary of the HIPAA Privacy Rule, "
    "https://www.hhs.gov/hipaa/for-professionals/privacy/laws-regulations/index.html."
)
_QUESTION = (
    "What may a covered entity use health information for, and what does "
    "the minimum necessary standard require?"
)


def _live_requested() -> bool:
    return os.getenv(LIVE_ENV, "").strip() == "1"


def _compliance_state() -> dict[str, Any]:
    return {
        "question": _QUESTION,
        "context": [
            {
                "source_document": "compliance-reference",
                "section": "US clinics: HIPAA permitted uses and disclosures",
                "text": _COMPLIANCE_CONTEXT,
            }
        ],
        "answer": "",
        "error": "",
        "caller_is_authenticated": False,
        "sources": [],
        "ticket_clause": "",
        "lookup_failure": "",
        "ticket_id": "",
        "ticket_status": "",
        "approved_memory": [],
    }


@pytest.mark.skipif(not _live_requested(), reason=f"Set {LIVE_ENV}=1 for the local GGUF stream")
def test_real_model_releases_during_sampling_and_interrupt_stops_it() -> None:
    if GENERATION_API_KEY:
        pytest.fail(
            "GENERATION_API_KEY is set, so the agent generation path uses the "
            "remote chat API instead of the local GGUF stream."
        )
    model_file = MODELS_DIR / LOCAL_GENERATION_GGUF_FILENAME
    if not model_file.is_file() or model_file.stat().st_size <= 0:
        pytest.fail(f"Local GGUF is missing: {model_file}")

    completion_watch = LocalGenerationWatch()
    token = bind_local_generation_watch(completion_watch)
    try:
        completed = generate_from_context(_compliance_state())
    finally:
        reset_local_generation_watch(token)

    assert completion_watch.observations, "generate_from_context did not sample locally"
    first = completion_watch.observations[0]
    assert first.releases, "the gate released no text during sampling"
    assert first.content_chunks_after_first_release > 0
    assert first.iterator_closed is True
    assert first.interrupted is False
    assert completed["error"] == ""
    assert completed["answer"]

    released_during_sampling = "".join(first.releases)
    assert released_during_sampling
    assert first.withheld_text not in released_during_sampling or first.withheld_text == ""
    print(
        "LIVE_COMPLETION",
        {
            "generations": len(completion_watch.observations),
            "releases": len(first.releases),
            "content_chunks_after_first_release": first.content_chunks_after_first_release,
            "raw_chars": len(first.raw_text),
            "committed_chars": len(first.committed_text),
            "withheld": first.withheld_text,
            "finish_reason": first.terminal_finish_reason,
            "gate_stopped": first.gate_stopped,
        },
    )

    def _stop_after_first_release(_text: str) -> None:
        interrupt_watch.stop = True

    interrupt_watch = LocalGenerationWatch(on_release=_stop_after_first_release)
    token = bind_local_generation_watch(interrupt_watch)
    try:
        interrupted = generate_from_context(_compliance_state())
    finally:
        reset_local_generation_watch(token)

    assert len(interrupt_watch.observations) == 1
    stopped = interrupt_watch.observations[0]
    assert stopped.interrupted is True
    assert stopped.iterator_closed is True
    assert stopped.content_chunks_after_first_release == 0
    assert stopped.terminal_finish_reason is None
    assert len(stopped.raw_text) < len(first.raw_text)
    assert stopped.releases
    assert interrupted["error"] == ""
    print(
        "LIVE_INTERRUPT",
        {
            "raw_chars": len(stopped.raw_text),
            "committed_chars": len(stopped.committed_text),
            "withheld": stopped.withheld_text,
            "finish_reason": stopped.terminal_finish_reason,
            "chunks_after_release": stopped.content_chunks_after_first_release,
        },
    )
