"""Unit tests for HealthCore retrieve() and query() with no live Qdrant."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from data.pipelines.rag import (
    _build_generation_messages,
    _ensure_local_gguf,
    _has_lexical_support,
    _load_local_llm,
    embedding_backend,
    generate_answer,
    generation_backend,
    local_llm_is_loaded,
    query,
    retrieve,
    unsupported_policy_facts,
)
from data.process.rag import build_chunks, chunk_markdown_document, deterministic_point_id
from shared.healthcore_rag.config import (
    EMBEDDING_MODEL_ID,
    GENERATION_MODEL_ID,
    LOCAL_EMBEDDING_MODEL_ID,
    LOCAL_GENERATION_MODEL_ID,
    SOURCE_DOCUMENT_FILES,
)


class _FakeHit:
    def __init__(self, score: float, payload: dict | None) -> None:
        self.score = score
        self.payload = payload


def test_embedding_and_generation_model_ids_differ() -> None:
    assert EMBEDDING_MODEL_ID
    assert GENERATION_MODEL_ID
    assert EMBEDDING_MODEL_ID != GENERATION_MODEL_ID


def test_embedding_backend_is_local_fastembed_without_api_key() -> None:
    assert embedding_backend() == LOCAL_EMBEDDING_MODEL_ID
    assert generation_backend() == LOCAL_GENERATION_MODEL_ID
    assert embedding_backend() != generation_backend()
    assert embedding_backend() != f"api:{EMBEDDING_MODEL_ID}"
    assert embedding_backend() == "BAAI/bge-small-en-v1.5"
    assert generation_backend() == "Qwen2.5-3B-Instruct"


def test_deterministic_point_ids_are_stable() -> None:
    first = deterministic_point_id("appointment-policy", 1, "Cancellation policy")
    second = deterministic_point_id("appointment-policy", 1, "Cancellation policy")
    other = deterministic_point_id("appointment-policy", 2, "Automated reminders")
    assert first == second
    assert first != other


def test_each_authorized_document_produces_at_least_three_chunks() -> None:
    chunks = build_chunks()
    counts: dict[str, int] = {}
    for chunk in chunks:
        source_document = str(chunk["source_document"])
        counts[source_document] = counts.get(source_document, 0) + 1
        assert chunk["company"] == "healthcore"
        assert chunk["language"] == "en"
        assert chunk["source_document"] in SOURCE_DOCUMENT_FILES.values()
        assert chunk["section"]
        assert chunk["text"]
        assert "patient_id" not in chunk["text"].lower()
    assert set(counts) == set(SOURCE_DOCUMENT_FILES.values())
    assert all(count >= 3 for count in counts.values())


def test_chunking_keeps_medicare_exception_with_cancellation_fee() -> None:
    policy = (
        "# Appointment and Cancellation Policy\n\n"
        "Cancellation policy:\n"
        "- Cancelling more than 24 hours in advance: no charge.\n"
        "- Cancelling less than 24 hours in advance, or no-show: 50 USD "
        "(or 40 GBP in the UK) charge for private-pay patients.\n"
        "- Medicare or Medicaid patients: not charged a no-show fee, per "
        "regulation, but the incident is logged in their record.\n"
    )
    chunks = chunk_markdown_document(policy, "appointment-policy")
    cancellation = next(chunk for chunk in chunks if "Cancellation policy" in chunk["section"])
    assert "50 USD" in cancellation["text"]
    assert "Medicare or Medicaid patients: not charged a no-show fee" in cancellation["text"]


def test_retrieve_excludes_scores_below_min_score(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_hits = [
        _FakeHit(0.91, {"text": "Accepted commercial insurance in the United States.", "source_document": "insurance-coverage", "section": "US"}),
        _FakeHit(0.20, {"text": "Accepted commercial insurance in the United Kingdom.", "source_document": "insurance-coverage", "section": "UK"}),
    ]
    monkeypatch.setattr("data.pipelines.rag.embed", lambda _text: [0.1, 0.2])
    monkeypatch.setattr("data.pipelines.rag._search_scored_points", lambda _vector, _k: fake_hits)

    results = retrieve("Which insurance is accepted?", k=5, min_score=0.50)

    assert len(results) == 1
    assert results[0]["text"] == "Accepted commercial insurance in the United States."
    assert isinstance(results[0], dict)
    assert not hasattr(results[0], "score")


def test_retrieve_can_return_fewer_than_k_results(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_hits = [
        _FakeHit(0.80, {"text": "Internal referral completed-referral time.", "source_document": "referral-process", "section": "Process"}),
        _FakeHit(0.70, {"text": "Internal referral average time is 11 days.", "source_document": "referral-process", "section": "Time"}),
        _FakeHit(0.10, {"text": "Internal referral drop candidate.", "source_document": "referral-process", "section": "Other"}),
    ]
    monkeypatch.setattr("data.pipelines.rag.embed", lambda _text: [0.1, 0.2])
    monkeypatch.setattr("data.pipelines.rag._search_scored_points", lambda _vector, k: fake_hits[:k])

    results = retrieve("How long does an internal referral take?", k=5, min_score=0.60)

    assert len(results) == 2
    assert len(results) < 5
    assert [item["text"] for item in results] == [
        "Internal referral completed-referral time.",
        "Internal referral average time is 11 days.",
    ]


def test_retrieve_does_not_apply_lexical_filter_on_local_fastembed_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_hits = [
        _FakeHit(0.90, {"text": "Sourdough starter hydration percentages.", "source_document": "appointment-policy", "section": "Unrelated"}),
    ]
    monkeypatch.setattr("data.pipelines.rag.embed", lambda _text: [0.1, 0.2])
    monkeypatch.setattr("data.pipelines.rag._search_scored_points", lambda _vector, _k: fake_hits)

    results = retrieve("What is the capital of France?", k=5, min_score=0.22)

    assert len(results) == 1
    assert results[0]["text"] == "Sourdough starter hydration percentages."


def test_retrieve_returns_empty_list_when_all_scores_are_below_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_hits = [
        _FakeHit(0.11, {"text": "weak-a", "source_document": "appointment-policy"}),
        _FakeHit(0.09, {"text": "weak-b", "source_document": "appointment-policy"}),
    ]
    monkeypatch.setattr("data.pipelines.rag.embed", lambda _text: [0.1, 0.2])
    monkeypatch.setattr("data.pipelines.rag._search_scored_points", lambda _vector, _k: fake_hits)

    results = retrieve("What is the capital of France?", k=5, min_score=0.22)

    assert results == []


def test_retrieve_returns_payload_dictionaries_not_sdk_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_hits = [
        _FakeHit(
            0.88,
            {
                "company": "healthcore",
                "source_document": "new-patient-checklist",
                "section": "Documents the patient should bring on the day of the appointment",
                "language": "en",
                "chunk_index": 1,
                "text": "Bring a valid ID document.",
            },
        )
    ]
    monkeypatch.setattr("data.pipelines.rag.embed", lambda _text: [0.1, 0.2])
    monkeypatch.setattr("data.pipelines.rag._search_scored_points", lambda _vector, _k: fake_hits)

    results = retrieve("What should someone bring to a first appointment?", k=3, min_score=0.20)

    assert results == [
        {
            "company": "healthcore",
            "source_document": "new-patient-checklist",
            "section": "Documents the patient should bring on the day of the appointment",
            "language": "en",
            "chunk_index": 1,
            "text": "Bring a valid ID document.",
        }
    ]
    assert type(results[0]) is dict


def test_query_returns_generation_output_not_raw_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_chunk = "Cancelling less than 24 hours in advance, or no-show: 50 USD"
    monkeypatch.setattr(
        "data.pipelines.rag.retrieve",
        lambda _question, **_kwargs: [{"text": raw_chunk, "source_document": "appointment-policy"}],
    )
    monkeypatch.setattr(
        "data.pipelines.rag.generate_answer",
        lambda _question, context: "Generated coordinator answer",
    )

    answer = query("Is there a charge for cancelling 12 hours in advance?")

    assert answer == "Generated coordinator answer"
    assert raw_chunk not in answer


def test_query_no_result_still_goes_through_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr("data.pipelines.rag.retrieve", lambda _question, **_kwargs: [])

    def fake_generate(question: str, context: list[dict]) -> str:
        captured["question"] = question
        captured["context"] = context
        return (
            "The available knowledge base does not contain enough information "
            "to answer that question."
        )

    monkeypatch.setattr("data.pipelines.rag.generate_answer", fake_generate)

    answer = query("What is the capital of France?")

    assert captured["context"] == []
    assert "does not contain enough information" in answer
    assert "Medicare" not in answer
    assert "50 USD" not in answer


def test_generate_answer_prompt_uses_only_context_and_coordinator_voice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_complete(messages: list[dict[str, str]]) -> str:
        captured["messages"] = messages
        return "HealthCore generated answer"

    monkeypatch.setattr("data.pipelines.rag.GENERATION_API_KEY", "test-placeholder-not-used")
    monkeypatch.setattr("data.pipelines.rag._complete_chat", fake_complete)

    context = [
        {
            "source_document": "insurance-coverage",
            "section": "United States (Texas, Florida, Georgia)",
            "text": "Medicare: accepted at all US clinics.",
        }
    ]
    answer = generate_answer("Which insurance is accepted?", context)

    assert answer == "HealthCore generated answer"
    messages = captured["messages"]
    assert isinstance(messages, list)
    system = messages[0]["content"]
    user = messages[1]["content"]
    assert "patient coordinator" in system
    assert "Use ONLY the retrieved context" in system
    assert "50 USD" not in system
    assert "Tom Callahan" not in system
    assert "11 days" not in system
    assert "Medicare: accepted at all US clinics." in user
    assert "insurance-coverage" in user


def test_paraphrased_first_appointment_question_has_lexical_support() -> None:
    payload = {
        "section": "Documents the patient should bring on the day of the appointment",
        "text": (
            "Documents the patient should bring on the day of the appointment:\n"
            "- A valid ID document.\n"
            "- Insurance card (if applicable).\n"
            "- List of current medications, if warranted by the reason for the visit."
        ),
    }
    assert _has_lexical_support("What should someone bring to a first appointment?", payload)


def test_lexical_filter_is_not_applied_when_embedding_api_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_hits = [
        _FakeHit(
            0.90,
            {
                "text": "Sourdough starter hydration percentages.",
                "source_document": "appointment-policy",
                "section": "Unrelated",
            },
        )
    ]
    monkeypatch.setattr("data.pipelines.rag.EMBEDDING_API_KEY", "test-placeholder-not-used")
    monkeypatch.setattr("data.pipelines.rag.embed", lambda _text: [0.1, 0.2])
    monkeypatch.setattr("data.pipelines.rag._search_scored_points", lambda _vector, _k: fake_hits)

    results = retrieve("What is the capital of France?", k=5, min_score=0.22)

    assert len(results) == 1
    assert results[0]["text"] == "Sourdough starter hydration percentages."


def test_generate_answer_invokes_local_llm_with_retrieved_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_chunk = (
        "Cancellation policy:\n"
        "- Cancelling less than 24 hours in advance, or no-show: 50 USD "
        "(or 40 GBP in the UK) charge for private-pay patients.\n"
        "- Medicare or Medicaid patients: not charged a no-show fee, per regulation."
    )
    captured: dict[str, object] = {}

    def fake_local(messages: list[dict[str, str]]) -> str:
        captured["messages"] = messages
        return "Cancelling 12 hours ahead is a late cancellation under the retrieved policy."

    monkeypatch.setattr("data.pipelines.rag._local_llm_complete", fake_local)

    context = [
        {
            "source_document": "appointment-policy",
            "section": "Cancellation policy",
            "text": raw_chunk,
        }
    ]
    answer = generate_answer("Is there a charge for cancelling 12 hours in advance?", context)

    assert answer != raw_chunk
    assert answer == "Cancelling 12 hours ahead is a late cancellation under the retrieved policy."
    assert generation_backend() == LOCAL_GENERATION_MODEL_ID
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert raw_chunk in messages[1]["content"]
    assert "appointment-policy" in messages[1]["content"]


def test_generate_answer_empty_context_calls_generation_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_local(messages: list[dict[str, str]]) -> str:
        captured["messages"] = messages
        return (
            "The available knowledge base does not contain enough information "
            "to answer that question."
        )

    monkeypatch.setattr("data.pipelines.rag._local_llm_complete", fake_local)

    answer = generate_answer("Do you accept an undocumented insurer?", [])

    assert captured["messages"]
    user = captured["messages"][1]["content"]
    assert "no retrieved HealthCore chunks" in user
    assert "does not contain enough information" in answer
    assert "yes" not in answer.lower()


def test_generate_answer_empty_context_rejects_invented_corpus_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "data.pipelines.rag._local_llm_complete",
        lambda _messages: "Yes, we accept Blue Cross and the no-show fee is 50 USD.",
    )

    answer = generate_answer("What is the capital of France?", [])

    assert "does not contain enough information" in answer
    assert "50 USD" not in answer
    assert "Blue Cross" not in answer


def test_static_prompt_contains_no_company_policy_facts() -> None:
    messages = _build_generation_messages(
        "How long does an internal referral take?",
        [{"source_document": "referral-process", "section": "Time", "text": "Target time is 11 days."}],
    )
    system = messages[0]["content"]
    for leaked in ("50 USD", "40 GBP", "Tom Callahan", "Marcus Reid", "Blue Cross", "Georgia"):
        assert leaked not in system


def test_unsupported_policy_facts_detect_cross_topic_leaks() -> None:
    context = [
        {
            "source_document": "referral-process",
            "section": "Target completed-referral time",
            "text": "Target completed-referral time: 11 days from creation to confirmed appointment.",
        }
    ]
    leaked = unsupported_policy_facts(
        "Referrals take 11 days. The late-cancellation fee is 50 USD and billing is Tom Callahan.",
        context,
    )
    assert "50 usd" in leaked
    assert "tom callahan" in leaked
    assert "11 days" not in leaked


def test_referral_only_context_retries_away_from_cancellation_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = [
        "Internal referrals take 11 days. Cancelling late costs 50 USD and you should call Tom Callahan.",
        "An internal referral currently averages 11 days from creation to a confirmed appointment.",
    ]

    def fake_local(_messages: list[dict[str, str]]) -> str:
        return answers.pop(0)

    monkeypatch.setattr("data.pipelines.rag._local_llm_complete", fake_local)
    context = [
        {
            "source_document": "referral-process",
            "section": "Target completed-referral time",
            "text": "Target completed-referral time: 11 days from creation to confirmed appointment.",
        }
    ]
    answer = generate_answer("How long does an internal referral take?", context)
    assert answer == "An internal referral currently averages 11 days from creation to a confirmed appointment."
    assert "50 USD" not in answer
    assert "Tom Callahan" not in answer


def test_checklist_only_context_retries_away_from_unrelated_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = [
        "Bring an ID. Also Medicaid is accepted in Georgia and no-show fees are 50 USD.",
        "Please bring a valid ID document, an insurance card if applicable, and a current medication list.",
    ]
    monkeypatch.setattr("data.pipelines.rag._local_llm_complete", lambda _messages: answers.pop(0))
    context = [
        {
            "source_document": "new-patient-checklist",
            "section": "Documents the patient should bring on the day of the appointment",
            "text": (
                "Documents the patient should bring on the day of the appointment:\n"
                "- A valid ID document.\n"
                "- Insurance card (if applicable).\n"
                "- List of current medications, if warranted by the reason for the visit."
            ),
        }
    ]
    answer = generate_answer("What should someone bring to a first appointment?", context)
    assert "valid ID" in answer
    assert "50 USD" not in answer
    assert "Georgia" not in answer


def test_twelve_hour_cancellation_retries_when_model_uses_wrong_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = [
        "No, there is no charge for cancelling more than 24 hours in advance.",
        "Cancelling 12 hours ahead is less than 24 hours, so private-pay patients are charged 50 USD.",
    ]
    monkeypatch.setattr("data.pipelines.rag._local_llm_complete", lambda _messages: answers.pop(0))
    context = [
        {
            "source_document": "appointment-policy",
            "section": "Cancellation policy",
            "text": (
                "Cancelling more than 24 hours in advance: no charge. "
                "Cancelling less than 24 hours in advance, or no-show: 50 USD "
                "charge for private-pay patients."
            ),
        }
    ]
    answer = generate_answer("Is there a charge for cancelling 12 hours in advance?", context)
    assert "50 USD" in answer
    assert "less than 24" in answer


def test_twelve_hour_contradictory_no_retries_for_direct_polarity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = [
        (
            "No, there is no charge for cancelling more than 24 hours in advance. "
            "For cancellations less than 24 hours, there is a charge of 50 USD "
            "for private-pay patients."
        ),
        (
            "Yes, cancelling 12 hours in advance is less than 24 hours, so "
            "private-pay patients are charged 50 USD. Medicare or Medicaid "
            "patients are not charged a no-show fee."
        ),
    ]
    monkeypatch.setattr("data.pipelines.rag._local_llm_complete", lambda _messages: answers.pop(0))
    context = [
        {
            "source_document": "appointment-policy",
            "section": "Cancellation policy",
            "text": (
                "Cancelling more than 24 hours in advance: no charge. "
                "Cancelling less than 24 hours in advance, or no-show: 50 USD "
                "charge for private-pay patients. Medicare or Medicaid patients: "
                "not charged a no-show fee, per regulation."
            ),
        }
    ]
    answer = generate_answer("Is there a charge for cancelling 12 hours in advance?", context)
    assert not answer.lstrip().lower().startswith("no")
    assert "12" in answer
    assert "50 USD" in answer
    assert "Medicare" in answer or "Medicaid" in answer
    assert "Marcus Reid" not in answer
    assert "referral" not in answer.lower()


def test_twelve_hour_retries_when_medicare_exception_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = [
        (
            "Yes, cancelling 12 hours in advance is less than 24 hours, so "
            "private-pay patients are charged 50 USD."
        ),
        (
            "Yes, cancelling 12 hours in advance is less than 24 hours, so "
            "private-pay patients are charged 50 USD. Medicare or Medicaid "
            "patients are not charged a no-show fee."
        ),
    ]
    monkeypatch.setattr("data.pipelines.rag._local_llm_complete", lambda _messages: answers.pop(0))
    context = [
        {
            "source_document": "appointment-policy",
            "section": "Cancellation policy",
            "text": (
                "Cancelling less than 24 hours in advance, or no-show: 50 USD "
                "charge for private-pay patients. Medicare or Medicaid patients: "
                "not charged a no-show fee, per regulation."
            ),
        }
    ]
    answer = generate_answer("Is there a charge for cancelling 12 hours in advance?", context)
    assert "50 USD" in answer
    assert "Medicare" in answer or "Medicaid" in answer
    assert not answer.lstrip().lower().startswith("no")


def test_cancellation_only_context_keeps_fee_and_medicare_exemption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "data.pipelines.rag._local_llm_complete",
        lambda _messages: (
            "Cancelling 12 hours ahead is less than 24 hours, so private-pay patients "
            "are charged 50 USD. Medicare or Medicaid patients are not charged a no-show fee."
        ),
    )
    context = [
        {
            "source_document": "appointment-policy",
            "section": "Cancellation policy",
            "text": (
                "Cancelling less than 24 hours in advance, or no-show: 50 USD "
                "charge for private-pay patients. Medicare or Medicaid patients: "
                "not charged a no-show fee, per regulation."
            ),
        }
    ]
    answer = generate_answer("Is there a charge for cancelling 12 hours in advance?", context)
    assert "50 USD" in answer
    assert "not charged a no-show fee" in answer
    assert generation_backend() == LOCAL_GENERATION_MODEL_ID


def test_insurance_only_context_does_not_keep_cancellation_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = [
        "US clinics accept Blue Cross. The no-show fee is 50 USD.",
        "US clinics accept Blue Cross Blue Shield for commercial coverage.",
    ]
    monkeypatch.setattr("data.pipelines.rag._local_llm_complete", lambda _messages: answers.pop(0))
    context = [
        {
            "source_document": "insurance-coverage",
            "section": "United States (Texas, Florida, Georgia)",
            "text": "Accepted commercial insurance: Blue Cross Blue Shield, Aetna, Cigna, UnitedHealthcare.",
        }
    ]
    answer = generate_answer("Which insurance is accepted?", context)
    assert "Blue Cross" in answer
    assert "50 USD" not in answer


def test_georgia_medicaid_uses_retrieved_limitation_instead_of_a_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers = [
        "The knowledge base does not contain enough information about Medicaid in Georgia.",
        "Medicaid is accepted only at Texas and Florida clinics, not currently at Georgia locations.",
    ]
    monkeypatch.setattr("data.pipelines.rag._local_llm_complete", lambda _messages: answers.pop(0))
    context = [
        {
            "source_document": "insurance-coverage",
            "section": "United States (Texas, Florida, Georgia)",
            "text": (
                "Medicare: accepted at all US clinics. Medicaid: accepted only at "
                "Texas and Florida clinics, not currently at Georgia locations."
            ),
        }
    ]
    answer = generate_answer("Is Medicaid accepted at Georgia clinics?", context)
    assert "not currently at Georgia" in answer or "not accepted" in answer.lower()
    assert "does not contain enough information" not in answer


def test_in_corpus_answer_still_passes_through_local_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []

    def fake_local(messages: list[dict[str, str]]) -> str:
        called.append(messages[-1]["content"])
        return "From the retrieved referral policy, the average is 11 days."

    monkeypatch.setattr("data.pipelines.rag._local_llm_complete", fake_local)
    answer = generate_answer(
        "How long does an internal referral take?",
        [{"source_document": "referral-process", "section": "Time", "text": "Target completed-referral time: 11 days."}],
    )
    assert called
    assert answer == "From the retrieved referral policy, the average is 11 days."
    assert generation_backend() == LOCAL_GENERATION_MODEL_ID


def test_failed_gguf_download_raises_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import data.pipelines.rag as rag

    monkeypatch.setattr(rag, "_local_gguf_path", lambda: rag.MODELS_DIR / "missing.gguf")

    def boom(**_kwargs: object) -> str:
        raise RuntimeError("simulated hub outage")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", boom)

    with pytest.raises(RuntimeError, match="Required repository") as error:
        _ensure_local_gguf()
    message = str(error.value)
    assert "Qwen/Qwen2.5-3B-Instruct-GGUF" in message
    assert "qwen2.5-3b-instruct-q4_k_m.gguf" in message
    assert "RAG_MODELS_DIR" in message
    assert "Do not commit model binaries" in message
    assert error.value.__cause__ is not None


def test_local_llm_is_reused_after_first_load(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    import data.pipelines.rag as rag

    builds = {"count": 0}

    class _FakeLlama:
        def __init__(self, **_kwargs: object) -> None:
            builds["count"] += 1

    rag._local_llm = None
    monkeypatch.setattr(rag, "_ensure_local_gguf", lambda: rag.MODELS_DIR / "cached.gguf")
    monkeypatch.setitem(sys.modules, "llama_cpp", SimpleNamespace(Llama=_FakeLlama))

    first = _load_local_llm()
    second = _load_local_llm()
    assert first is second
    assert builds["count"] == 1
    assert local_llm_is_loaded() is True
    rag._local_llm = None
