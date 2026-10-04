"""In-memory chat sessions and one pub/sub channel per session.

The generation worker is the only caller of the agent. Socket handlers
subscribe to ``chat.<session_id>`` and do not call the model themselves.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.agent.graph import run_support_agent
from data.pipelines.rag import (
    LocalGenerationWatch,
    bind_generation_conversation,
    bind_local_generation_watch,
    reset_generation_conversation,
    reset_local_generation_watch,
)

AGENT_ID = "compliance_assistant"
CHANNEL_PREFIX = "chat."


@dataclass
class ChatMessage:
    message_id: str
    role: str
    text: str
    status: str = "completed"


@dataclass
class ChatSession:
    session_id: str
    user_id: str
    created_at: str
    agent_id: str = AGENT_ID
    status: str = "active"
    messages: list[ChatMessage] = field(default_factory=list)
    generating: bool = False
    pending_new_input: str = ""
    cancel_requested: bool = False
    bound_thread_id: str = ""
    last_generation: dict[str, Any] = field(default_factory=dict)

    @property
    def thread_id(self) -> str:
        """The LangGraph thread id is the chat session id. There is no second id."""
        return self.session_id


class SessionHub:
    """Fan-out session events to every subscribed socket queue."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, ChatSession] = {}
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._watches: dict[str, LocalGenerationWatch] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self.generation_starts: dict[str, int] = {}
        self.thread_ids: list[str] = []

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def reset(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._subscribers.clear()
            self._watches.clear()
            self.generation_starts.clear()
            self.thread_ids.clear()

    def channel_name(self, session_id: str) -> str:
        return f"{CHANNEL_PREFIX}{session_id}"

    def get_session(self, session_id: str) -> ChatSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def open_session(self, session_id: str, user_id: str) -> ChatSession | None:
        """Return the session for this staff user, or None when another user owns it."""
        with self._lock:
            existing = self._sessions.get(session_id)
            if existing is None:
                created = ChatSession(
                    session_id=session_id,
                    user_id=user_id,
                    created_at=datetime.now(UTC).isoformat(),
                )
                self._sessions[session_id] = created
                return created
            if existing.user_id != user_id:
                return None
            return existing

    def subscribe(self, session_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        with self._lock:
            self._subscribers.setdefault(session_id, []).append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            subscribers = self._subscribers.get(session_id, [])
            if queue in subscribers:
                subscribers.remove(queue)

    def publish(self, session_id: str, event: dict[str, Any]) -> None:
        loop = self._loop
        if loop is None:
            return
        with self._lock:
            subscribers = list(self._subscribers.get(session_id, []))
        for queue in subscribers:
            loop.call_soon_threadsafe(queue.put_nowait, event)

    def snapshot_event(self, session: ChatSession) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        for message in session.messages:
            payload: dict[str, Any] = {
                "message_id": message.message_id,
                "role": message.role,
                "text": message.text,
            }
            if message.role == "assistant" and message.status == "interrupted":
                payload["status"] = "interrupted"
            messages.append(payload)
        return {
            "event": "session_snapshot",
            "data": {"session_id": session.session_id, "messages": messages},
        }

    def active_watch(self, session_id: str) -> LocalGenerationWatch | None:
        with self._lock:
            return self._watches.get(session_id)

    def conversation_before_latest_user(self, session: ChatSession) -> list[dict[str, str]]:
        """Prior turns for the prompt. The newest user question stays the current question."""
        user_indexes = [index for index, message in enumerate(session.messages) if message.role == "user"]
        if not user_indexes:
            return []
        prior = session.messages[: user_indexes[-1]]
        return [
            {"role": message.role, "content": message.text}
            for message in prior
            if message.text
        ]


_HUB = SessionHub()


def get_chat_hub() -> SessionHub:
    return _HUB


def reset_chat_hub_for_tests() -> None:
    _HUB.reset()


def _generation_report(watch: LocalGenerationWatch) -> dict[str, Any]:
    """Record how the kept sample relates to the assistant turn.

    This is test evidence. It is not a public chat event.
    """
    return {
        "kept_attempt_index": watch.kept_attempt_index,
        "replayed_kept_attempt": watch.replayed_kept_attempt,
        "replacement_unpublished": watch.replacement_unpublished,
        "discarded_attempt_text": watch.discarded_attempt_text,
        "replaced_kept_text": watch.replaced_kept_text,
        "published_text": watch.published_text,
        "interrupted": watch.interrupted,
        "attempts": [
            {
                "content_chunks_after_first_release": item.content_chunks_after_first_release,
                "published_before_iterator_close": item.published_before_iterator_close,
                "withheld_text": item.withheld_text,
                "interrupted": item.interrupted,
                "iterator_closed": item.iterator_closed,
                "finish_reason": item.terminal_finish_reason,
                "release_count": len(item.releases),
                "prompt_messages": item.prompt_messages,
            }
            for item in watch.observations
        ],
    }


def _message_id() -> str:
    return "msg_" + uuid.uuid4().hex[:12]


def start_user_turn(session_id: str, text: str) -> bool:
    """Publish one user turn and start one generation. Return False when one is already running."""
    hub = get_chat_hub()
    session = hub.get_session(session_id)
    loop = hub._loop
    if session is None or loop is None or not text.strip():
        return False
    with hub._lock:
        if session.generating:
            return False
        session.generating = True
        session.pending_new_input = ""
        session.cancel_requested = False
        session.status = "active"
        session.messages.append(
            ChatMessage(message_id=_message_id(), role="user", text=text, status="completed")
        )
    hub.publish(
        session_id,
        {"event": "user_message", "data": {"session_id": session_id, "text": text}},
    )
    threading.Thread(
        target=_generate_turn,
        args=(session_id, text),
        name=f"chat-generation-{session_id}",
        daemon=True,
    ).start()
    return True


def request_interrupt(session_id: str, new_input: str) -> None:
    """Stop the active sample. ``new_input`` becomes the next user turn after it stops."""
    hub = get_chat_hub()
    session = hub.get_session(session_id)
    watch = hub.active_watch(session_id)
    if session is None:
        return
    with hub._lock:
        session.pending_new_input = new_input
        session.cancel_requested = True
        session.status = "interrupted"
    if watch is not None:
        watch.request_stop()


def _generate_turn(session_id: str, question: str) -> None:
    hub = get_chat_hub()
    session = hub.get_session(session_id)
    if session is None:
        return
    watch = LocalGenerationWatch()
    assistant = ChatMessage(message_id=_message_id(), role="assistant", text="", status="in_progress")
    sequence = 0

    def publish_kept(token: str) -> None:
        nonlocal sequence
        sequence += 1
        assistant.text += token
        hub.publish(
            session_id,
            {
                "event": "token_chunk",
                "data": {"session_id": session_id, "token": token, "sequence": sequence},
            },
        )

    watch.on_kept_release = publish_kept
    with hub._lock:
        hub._watches[session_id] = watch
        if session.cancel_requested:
            watch.request_stop()
        session.messages.append(assistant)
        hub.generation_starts[session_id] = hub.generation_starts.get(session_id, 0) + 1
    prior = hub.conversation_before_latest_user(session)
    watch_token = bind_local_generation_watch(watch)
    conversation_token = bind_generation_conversation(prior)
    interrupted = False
    try:
        from app.agent.graph import checkpoint_database_path, trace_directory
        from app.agent.memory_store import memory_database_path

        outcome = run_support_agent(
            question,
            caller_is_authenticated=True,
            actor_user_id=session.user_id,
            thread_id=session.thread_id,
            checkpoint_path=checkpoint_database_path(),
            trace_dir=trace_directory(),
            memory_path=memory_database_path(),
        )
        hub.thread_ids.append(outcome.thread_id)
        session.bound_thread_id = outcome.thread_id
        interrupted = watch.interrupted
        session.last_generation = _generation_report(watch)
        if not interrupted:
            # Subscribers already have assistant.text from token_chunk events.
            # The agent may return a grounding retry that was not published.
            # That return value stays off the transcript, the snapshot, and
            # the next turn's conversation.
            if outcome.answer != assistant.text:
                session.last_generation["unpublished_agent_answer"] = outcome.answer
            assistant.status = "completed"
            session.status = "active"
            hub.publish(
                session_id,
                {
                    "event": "generation_completed",
                    "data": {"session_id": session_id, "message_id": assistant.message_id},
                },
            )
        else:
            assistant.status = "interrupted"
            session.status = "interrupted"
            hub.publish(
                session_id,
                {
                    "event": "generation_interrupted",
                    "data": {
                        "session_id": session_id,
                        "message_id": assistant.message_id,
                        "status": "interrupted",
                    },
                },
            )
        session.last_generation["stored_text"] = assistant.text
    finally:
        reset_generation_conversation(conversation_token)
        reset_local_generation_watch(watch_token)
        with hub._lock:
            hub._watches.pop(session_id, None)
            pending = session.pending_new_input
            session.pending_new_input = ""
            session.generating = False
        if pending.strip():
            loop = hub._loop
            if loop is not None:
                loop.call_soon_threadsafe(start_user_turn, session_id, pending)


def session_event_names() -> tuple[str, ...]:
    """Public chat events. Auth frames are not part of this contract."""
    return (
        "token_chunk",
        "interrupt_requested",
        "generation_interrupted",
        "generation_completed",
        "session_snapshot",
        "user_message",
    )
