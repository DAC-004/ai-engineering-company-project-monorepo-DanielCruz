"""The stored/reconnected transcript must match what subscribers received."""
import pytest
from app.services.chat_channel import ChatMessage, ChatSession, SessionHub, _finalize_successful_generation
from data.pipelines.rag import LocalGenerationWatch


@pytest.mark.parametrize("flag", ["replacement_unpublished", "replaced_kept_text"])
def test_unpublished_retry_cannot_replace_shared_transcript(flag, monkeypatch):
    hub = SessionHub()
    session = ChatSession(session_id="chat_shared", user_id="fictional-staff", created_at="2026-11-07")
    original = "The policy applies to this request."
    assistant = ChatMessage(message_id="msg_shared", role="assistant", text=original, status="in_progress")
    session.messages.append(assistant)
    watch = LocalGenerationWatch(published_text=original)
    setattr(watch, flag, True)
    events = []
    monkeypatch.setattr(hub, "publish", lambda _session_id, event: events.append(event))
    failures = []
    unpublished = original + " This additional statement was never sent to subscribers."
    assert _finalize_successful_generation(session.session_id, hub, session, assistant, watch, unpublished, lambda: failures.append(True))
    assert not failures
    assert assistant.text == original
    assert hub.snapshot_event(session)["data"]["messages"][0]["text"] == original
    assert session.last_generation["unpublished_agent_answer"] == unpublished
    assert [event["event"] for event in events] == ["generation_completed"]


def test_safe_extension_reaches_subscribers_before_becoming_history(monkeypatch):
    hub = SessionHub()
    session = ChatSession(session_id="chat_extension", user_id="fictional-staff", created_at="2026-11-07")
    original = "The policy applies."
    assistant = ChatMessage(message_id="msg_extension", role="assistant", text=original, status="in_progress")
    session.messages.append(assistant)
    watch = LocalGenerationWatch(published_text=original)
    released = []
    def publish(text):
        released.append(text)
        assistant.text += text
    watch.on_kept_release = publish
    monkeypatch.setattr(hub, "publish", lambda *_args: None)
    full = original + " Follow the documented process."
    assert _finalize_successful_generation(session.session_id, hub, session, assistant, watch, full, lambda: pytest.fail("unexpected generation failure"))
    assert assistant.text == original + "".join(released) == full
