"""Wiring tests for gated local generation.

A fake llama iterator checks ordering and interruption. It does not establish
real model streaming or cancellation.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.agent.nodes import generate_from_context
from data.pipelines.rag import (
    LocalGenerationWatch,
    bind_local_generation_watch,
    reset_local_generation_watch,
)

_ROLE_CHUNK: dict[str, Any] = {
    "choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]
}
_FIRST_SENTENCE = "The indexed referral target is 11 days. "
_SECOND_SENTENCE = "It runs from creation to a confirmed appointment."
_FINISH_CHUNK: dict[str, Any] = {"choices": [{"delta": {}, "finish_reason": "stop"}]}


class _ChunkIterator:
    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self.chunks = list(chunks)
        self.pulled = 0
        self.closed = False
        self._remaining = list(chunks)

    def __iter__(self) -> "_ChunkIterator":
        return self

    def __next__(self) -> dict[str, Any]:
        if not self._remaining:
            raise StopIteration
        self.pulled += 1
        return self._remaining.pop(0)

    def close(self) -> None:
        self.closed = True
        self._remaining.clear()


class _FakeLlama:
    def __init__(self) -> None:
        self.iterators: list[_ChunkIterator] = []
        self.stream_flags: list[bool] = []

    def create_chat_completion(self, **kwargs: Any) -> _ChunkIterator:
        self.stream_flags.append(bool(kwargs.get("stream")))
        iterator = _ChunkIterator(
            [
                _ROLE_CHUNK,
                {"choices": [{"delta": {"content": _FIRST_SENTENCE}, "finish_reason": None}]},
                {"choices": [{"delta": {"content": _SECOND_SENTENCE}, "finish_reason": None}]},
                _FINISH_CHUNK,
            ]
        )
        self.iterators.append(iterator)
        return iterator


def _install_fake_llm(monkeypatch: pytest.MonkeyPatch) -> _FakeLlama:
    fake = _FakeLlama()
    monkeypatch.setattr("data.pipelines.rag._load_local_llm", lambda: fake)
    monkeypatch.setattr("data.pipelines.rag.GENERATION_API_KEY", "")
    return fake


def _referral_state() -> dict[str, Any]:
    return {
        "question": "How long does an internal referral take?",
        "context": [
            {
                "source_document": "referral-process",
                "section": "Target completed-referral time",
                "text": (
                    "Target completed-referral time: 11 days from creation "
                    "to confirmed appointment."
                ),
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


def test_agent_generation_releases_text_before_the_iterator_is_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _install_fake_llm(monkeypatch)
    pulled_at_release: list[int] = []
    watch = LocalGenerationWatch(
        on_release=lambda _text: pulled_at_release.append(fake.iterators[-1].pulled)
    )
    token = bind_local_generation_watch(watch)
    try:
        result = generate_from_context(_referral_state())
    finally:
        reset_local_generation_watch(token)

    assert fake.stream_flags == [True]
    observation = watch.observations[0]
    assert observation.releases
    assert pulled_at_release
    assert fake.iterators[0].pulled > pulled_at_release[0]
    assert observation.content_chunks_after_first_release > 0
    assert observation.terminal_finish_reason == "stop"
    assert observation.iterator_closed is True
    assert observation.interrupted is False
    assert _FIRST_SENTENCE.strip() in "".join(observation.releases)
    assert result["answer"]
    assert not appears_prohibited(result["answer"])


def test_interrupt_stops_sampling_and_releases_nothing_further(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _install_fake_llm(monkeypatch)

    def _stop_on_first_release(_text: str) -> None:
        watch.stop = True

    watch = LocalGenerationWatch(on_release=_stop_on_first_release)
    token = bind_local_generation_watch(watch)
    try:
        generate_from_context(_referral_state())
    finally:
        reset_local_generation_watch(token)

    iterator = fake.iterators[0]
    observation = watch.observations[0]
    assert len(fake.iterators) == 1
    assert iterator.pulled == 2
    assert iterator.closed is True
    assert observation.interrupted is True
    assert observation.iterator_closed is True
    assert observation.content_chunks_after_first_release == 0
    assert _SECOND_SENTENCE not in observation.committed_text
    assert _SECOND_SENTENCE not in "".join(observation.releases)
    assert observation.terminal_finish_reason is None


class _ScriptedLlama:
    """Return a different completion for each call. Still not a real model."""

    def __init__(self, scripts: list[list[str]]) -> None:
        self._scripts = scripts
        self.iterators: list[_ChunkIterator] = []

    def create_chat_completion(self, **_kwargs: Any) -> _ChunkIterator:
        contents = self._scripts[len(self.iterators)]
        chunks: list[dict[str, Any]] = [_ROLE_CHUNK]
        chunks.extend(
            {"choices": [{"delta": {"content": piece}, "finish_reason": None}]}
            for piece in contents
        )
        chunks.append(_FINISH_CHUNK)
        iterator = _ChunkIterator(chunks)
        self.iterators.append(iterator)
        return iterator


def test_grounding_retry_does_not_append_the_replacement_to_the_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first sample streams immediately. The replacement is not concatenated.

    This uses a scripted model. It does not prove live sampling. The returned
    answer is still the retried text. The token stream stays the first sample
    because the contract has no retract event.
    """
    discarded = "DISCARDED_ATTEMPT_MARKER treatment is allowed."
    kept = (
        "A covered entity may use information for treatment. "
        "See https://www.hhs.gov/hipaa/for-professionals/privacy/laws-regulations/index.html. "
        "This is not a previously issued internal policy."
    )
    fake = _ScriptedLlama([[discarded], [kept]])
    monkeypatch.setattr("data.pipelines.rag._load_local_llm", lambda: fake)
    monkeypatch.setattr("data.pipelines.rag.GENERATION_API_KEY", "")
    published: list[str] = []
    closed_at_publish: list[bool] = []

    def _keep(text: str) -> None:
        published.append(text)
        closed_at_publish.append(fake.iterators[-1].closed)

    watch = LocalGenerationWatch(on_kept_release=_keep)
    token = bind_local_generation_watch(watch)
    try:
        from data.pipelines.rag import generate_answer

        answer = generate_answer(
            "What may a covered entity use health information for?",
            [
                {
                    "source_document": "compliance-reference",
                    "text": (
                        "Covered entities may use information for treatment. "
                        "https://www.hhs.gov/hipaa/for-professionals/privacy/laws-regulations/index.html. "
                        "This is not a claim that healthcore previously issued this rule."
                    ),
                }
            ],
        )
    finally:
        reset_local_generation_watch(token)

    published_text = "".join(published)
    assert len(fake.iterators) == 2
    assert watch.replayed_kept_attempt is False
    assert watch.replacement_unpublished is True
    assert watch.replaced_kept_text is True
    assert watch.observations[0].published_before_iterator_close is True
    assert closed_at_publish
    assert not any(closed_at_publish)
    assert "DISCARDED_ATTEMPT_MARKER" in published_text
    assert "previously issued internal policy" not in published_text
    assert "DISCARDED_ATTEMPT_MARKER" not in answer
    assert "https://www.hhs.gov/" in answer
    assert published_text + kept not in answer


def test_single_attempt_publishes_before_the_iterator_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A no-retry sample emits kept text while the iterator is still open."""
    fake = _install_fake_llm(monkeypatch)
    closed_at_publish: list[bool] = []
    pulled_at_publish: list[int] = []

    def _keep(_text: str) -> None:
        closed_at_publish.append(fake.iterators[-1].closed)
        pulled_at_publish.append(fake.iterators[-1].pulled)

    watch = LocalGenerationWatch(on_kept_release=_keep)
    token = bind_local_generation_watch(watch)
    try:
        generate_from_context(_referral_state())
    finally:
        reset_local_generation_watch(token)

    assert watch.replayed_kept_attempt is False
    assert watch.replacement_unpublished is False
    assert len(fake.iterators) == 1
    assert watch.observations[0].published_before_iterator_close is True
    assert watch.observations[0].content_chunks_after_first_release > 0
    assert closed_at_publish
    assert not any(closed_at_publish)
    assert fake.iterators[0].pulled > pulled_at_publish[0]


def test_interrupt_does_not_publish_releases_that_were_not_already_emitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stopping the sample leaves only the text already passed to on_kept_release."""
    fake = _install_fake_llm(monkeypatch)
    published: list[str] = []

    def _keep(text: str) -> None:
        published.append(text)
        watch.request_stop()

    watch = LocalGenerationWatch(on_kept_release=_keep)
    token = bind_local_generation_watch(watch)
    try:
        generate_from_context(_referral_state())
    finally:
        reset_local_generation_watch(token)

    assert watch.interrupted is True
    assert fake.iterators[0].closed is True
    assert published == [_FIRST_SENTENCE]
    assert _SECOND_SENTENCE not in "".join(published)
    assert watch.published_text == _FIRST_SENTENCE
    assert len(fake.iterators) == 1


def test_stop_from_another_thread_closes_the_fake_iterator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stop flag is visible across threads. The producer is still fake."""
    import threading

    fake = _install_fake_llm(monkeypatch)
    started = threading.Event()
    release = threading.Event()

    def _hold(_text: str) -> None:
        started.set()
        release.wait(5)

    watch = LocalGenerationWatch(on_release=_hold)

    def _run() -> None:
        token = bind_local_generation_watch(watch)
        try:
            generate_from_context(_referral_state())
        finally:
            reset_local_generation_watch(token)

    worker = threading.Thread(target=_run)
    worker.start()
    assert started.wait(5)
    watch.request_stop()
    release.set()
    worker.join(5)

    assert worker.is_alive() is False
    assert watch.interrupted is True
    assert fake.iterators[0].closed is True
    assert _SECOND_SENTENCE not in "".join(watch.observations[0].releases)


def test_bound_conversation_is_in_the_generation_prompt_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_llm(monkeypatch)
    from data.pipelines.rag import bind_generation_conversation, reset_generation_conversation

    watch = LocalGenerationWatch()
    watch_token = bind_local_generation_watch(watch)
    conversation_token = bind_generation_conversation(
        [
            {"role": "user", "content": "Earlier question about the minimum necessary standard."},
            {"role": "assistant", "content": "A covered"},
        ]
    )
    try:
        generate_from_context(_referral_state())
    finally:
        reset_generation_conversation(conversation_token)
        reset_local_generation_watch(watch_token)

    roles = [item["role"] for item in watch.observations[0].prompt_messages]
    contents = [item["content"] for item in watch.observations[0].prompt_messages]
    assert roles[:3] == ["system", "user", "assistant"]
    assert "Earlier question about the minimum necessary standard." in contents
    assert "A covered" in contents

    unbound = LocalGenerationWatch()
    unbound_token = bind_local_generation_watch(unbound)
    try:
        generate_from_context(_referral_state())
    finally:
        reset_local_generation_watch(unbound_token)
    assert [item["role"] for item in unbound.observations[0].prompt_messages] == ["system", "user"]


def appears_prohibited(text: str) -> bool:
    from app.agent.guardrails.text_rules import disclosure_is_prohibited
    from app.agent.memory_policy import appears_to_contain_phi

    return appears_to_contain_phi(text) or disclosure_is_prohibited(text)
