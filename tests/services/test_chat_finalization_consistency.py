"""Published tokens, stored turns and reconnect history must agree."""
from types import SimpleNamespace

import pytest

from app.services.chat_channel import ChatMessage, ChatSession, _finalize_successful_generation
from data.pipelines.rag import GenerationObservation, LocalGenerationWatch, _emit_kept_release


@pytest.mark.parametrize("kind", ["replacement", "retry_extension", "withheld_extension", "safe_extension"])
def test_completion_never_silently_replaces_or_appends_unpublished_text(kind):
    prefix = "Visible answer."
    suffix = " Additional approved context about the fictional internal referral process is available in the supplied policy."
    outcome = "A different unpublished replacement that is much longer than the visible answer and must not silently replace it." if kind == "replacement" else prefix + suffix
    assistant = ChatMessage("assistant-fixture", "assistant", "", "in_progress")
    session = ChatSession("chat_fixture", "fictional-user", "2026-11-07T00:00:00Z", messages=[assistant])
    events = []
    watch = LocalGenerationWatch()

    def publish(text):
        assistant.text += text
        events.append({"event": "token_chunk", "data": {"token": text}})

    watch.on_kept_release = publish
    _emit_kept_release(watch, prefix)
    if kind == "retry_extension":
        watch.replacement_unpublished = True
        watch.replaced_kept_text = True
    if kind == "withheld_extension":
        watch.observations.append(GenerationObservation(gate_stopped=True, withheld_text=suffix))
    failed = []
    hub = SimpleNamespace(publish=lambda _sid, event: events.append(event))
    assert _finalize_successful_generation(session.session_id, hub, session, assistant, watch, outcome, lambda: failed.append(True))
    visible = "".join(e["data"]["token"] for e in events if e["event"] == "token_chunk")
    expected = outcome if kind == "safe_extension" else prefix
    assert assistant.text == visible == expected
    assert session.last_generation["stored_text"] == expected
    assert events[-1]["event"] == "generation_completed"
    assert not failed
