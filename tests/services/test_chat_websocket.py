"""WebSocket contract tests.

The agent in this file is a stand-in. Passing these tests does not prove that
the local GGUF streamed or cancelled. Live evidence is in
tests/pipelines/test_live_chat_websocket.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest
import uvicorn
import websockets
from fastapi import FastAPI
from websockets.exceptions import ConnectionClosed, InvalidStatus

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.agent.graph import AgentRun  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.db.database import reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.routers.chat import router  # noqa: E402
from app.schemas.user import UserCreate, UserRole  # noqa: E402
from app.services import user_service  # noqa: E402
from app.services.chat_channel import get_chat_hub, reset_chat_hub_for_tests, session_event_names  # noqa: E402

_FIRST_QUESTION = "What does the minimum necessary standard require?"
_NEW_INPUT = "Limit the answer to the purpose of the requested use."
_PARTIAL = "The minimum necessary standard "
_REST = "limits the information to the purpose."


@pytest.fixture
def isolated_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "incidents.json"))
    monkeypatch.setenv("SECRET_KEY", "isolated-chat-secret-key-32bytes")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'inventory.db').as_posix()}")
    get_settings.cache_clear()
    reset_db_for_tests()
    reset_engine_for_tests()
    reset_chat_hub_for_tests()
    monkeypatch.setattr(
        "app.agent.graph.checkpoint_database_path",
        lambda: tmp_path / "checkpoints" / "support_agent.sqlite",
    )
    monkeypatch.setattr(
        "app.agent.graph.trace_directory",
        lambda: tmp_path / "traces",
    )
    monkeypatch.setattr(
        "app.agent.memory_store.memory_database_path",
        lambda: tmp_path / "memory" / "operational.sqlite",
    )
    yield
    reset_chat_hub_for_tests()
    reset_db_for_tests()
    reset_engine_for_tests()
    get_settings.cache_clear()


def _staff_token(email: str) -> str:
    user = user_service.create_user(
        UserCreate(email=email, password="test-password-1"),
        role=UserRole.manager,
    )
    return create_access_token(subject=user.id)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class _ChatServer:
    def __init__(self) -> None:
        self.port = _free_port()
        self._stop = threading.Event()
        application = FastAPI()
        application.include_router(router)
        config = uvicorn.Config(
            application,
            host="127.0.0.1",
            port=self.port,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self) -> None:
        self._thread.start()
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), 0.2):
                    return
            except OSError:
                time.sleep(0.05)
        raise RuntimeError("chat test server did not start")

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(5)

    def url(self, session_id: str, token: str | None = None) -> str:
        base = f"ws://127.0.0.1:{self.port}/ws/chat/{session_id}"
        if token is None:
            return base
        return f"{base}?token={token}"


class _StaffSocket:
    """Open a chat socket and authenticate with the first auth frame.

    The URL has no query string, so a real JWT is not written to the access log.
    """

    def __init__(self, server: _ChatServer, session_id: str, token: str) -> None:
        self._url = server.url(session_id)
        self._token = token
        self._connection: Any = None

    async def __aenter__(self) -> Any:
        self._connection = await websockets.connect(self._url)
        await self._connection.send(
            json.dumps({"event": "auth", "data": {"token": self._token}})
        )
        return self._connection

    async def __aexit__(self, *_exc: object) -> None:
        if self._connection is not None:
            await self._connection.close()


@pytest.fixture
def chat_server(isolated_stores: None):
    server = _ChatServer()
    server.start()
    yield server
    server.stop()


def _install_fake_agent(monkeypatch: pytest.MonkeyPatch, script: dict[str, Any]) -> dict[str, Any]:
    """Replace the agent with a controllable publisher. This is not the GGUF."""

    def _run(question: str, *, thread_id: str | None = None, **_kwargs: Any) -> AgentRun:
        from data.pipelines.rag import _GENERATION_CONVERSATION, _LOCAL_GENERATION_WATCH

        watch = _LOCAL_GENERATION_WATCH.get()
        script["calls"].append(
            {
                "question": question,
                "thread_id": thread_id,
                "conversation": _GENERATION_CONVERSATION.get(),
            }
        )
        if watch is not None:
            watch.forward_kept = True
            if watch.on_kept_release is not None:
                watch.on_kept_release(_PARTIAL)
            if script["block_first"] and len(script["calls"]) == 1:
                script["first_token"].set()
                script["release"].wait(5)
                if watch.stop_requested():
                    watch.interrupted = True
                    return AgentRun(
                        answer=_PARTIAL,
                        error="",
                        trace_id="mock-trace",
                        thread_id=thread_id or "",
                    )
            if watch.on_kept_release is not None:
                watch.on_kept_release(_REST)
        return AgentRun(
            answer=_PARTIAL + _REST,
            error="",
            trace_id="mock-trace",
            thread_id=thread_id or "",
        )

    script.setdefault("calls", [])
    script.setdefault("block_first", False)
    script.setdefault("first_token", threading.Event())
    script.setdefault("release", threading.Event())
    monkeypatch.setattr("app.services.chat_channel.run_support_agent", _run)
    return script


async def _recv_json(connection: Any, timeout: float = 5) -> dict[str, Any]:
    raw = await asyncio.wait_for(connection.recv(), timeout)
    payload = json.loads(raw)
    assert isinstance(payload, dict)
    return payload


async def _collect_until(
    connection: Any,
    event_name: str,
    timeout: float = 5,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        events.append(await _recv_json(connection, timeout=deadline - time.time()))
        if events[-1]["event"] == event_name:
            return events
    raise AssertionError(f"did not receive {event_name}: {events}")


def test_public_event_names_match_the_healthcore_contract() -> None:
    assert session_event_names() == (
        "token_chunk",
        "interrupt_requested",
        "generation_interrupted",
        "generation_completed",
        "session_snapshot",
        "user_message",
    )


def test_missing_jwt_is_rejected_before_a_chat_event(chat_server: _ChatServer) -> None:
    async def _run() -> list[dict[str, Any]]:
        received: list[dict[str, Any]] = []
        async with websockets.connect(chat_server.url("chat_missing_jwt")) as connection:
            await connection.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": "chat_missing_jwt", "text": _FIRST_QUESTION},
                    }
                )
            )
            try:
                received.append(await _recv_json(connection, timeout=2))
            except (ConnectionClosed, TimeoutError, asyncio.TimeoutError):
                return received
        return received

    received = asyncio.run(_run())
    assert received == []
    assert get_chat_hub().get_session("chat_missing_jwt") is None


def test_invalid_jwt_is_rejected_before_a_chat_event(chat_server: _ChatServer) -> None:
    async def _run() -> None:
        async with websockets.connect(
            chat_server.url("chat_invalid_jwt", "not-a-backoffice-jwt")
        ) as connection:
            await _recv_json(connection, timeout=2)

    with pytest.raises(InvalidStatus) as rejection:
        asyncio.run(_run())
    assert rejection.value.response.status_code == 403
    assert get_chat_hub().get_session("chat_invalid_jwt") is None


def test_invalid_auth_frame_is_rejected_before_a_chat_event(chat_server: _ChatServer) -> None:
    async def _run() -> list[dict[str, Any]]:
        received: list[dict[str, Any]] = []
        async with websockets.connect(chat_server.url("chat_bad_frame")) as connection:
            await connection.send(json.dumps({"event": "auth", "data": {"token": "not-a-jwt"}}))
            try:
                received.append(await _recv_json(connection, timeout=2))
            except (ConnectionClosed, TimeoutError, asyncio.TimeoutError):
                return received
        return received

    assert asyncio.run(_run()) == []


def test_auth_frame_logs_omit_the_jwt(chat_server: _ChatServer) -> None:
    token = _staff_token("staff.logs@example.com")
    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record.getMessage())

    handler = _Capture()
    loggers = [
        logging.getLogger("uvicorn.access"),
        logging.getLogger("uvicorn.error"),
        logging.getLogger("healthcore.chat"),
    ]
    previous_levels = [item.level for item in loggers]
    for item in loggers:
        item.addHandler(handler)
        item.setLevel(logging.INFO)

    async def _exercise() -> str:
        async with _StaffSocket(chat_server, "chat_logs", token) as connection:
            snapshot = await _recv_json(connection)
        assert snapshot["event"] == "session_snapshot"
        async with websockets.connect(chat_server.url("chat_logs_missing")) as connection:
            await connection.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": "chat_logs_missing", "text": _FIRST_QUESTION},
                    }
                )
            )
            try:
                await _recv_json(connection, timeout=2)
            except (ConnectionClosed, TimeoutError, asyncio.TimeoutError):
                pass
        async with websockets.connect(chat_server.url("chat_logs_bad")) as connection:
            await connection.send(json.dumps({"event": "auth", "data": {"token": "not-a-jwt"}}))
            try:
                await _recv_json(connection, timeout=2)
            except (ConnectionClosed, TimeoutError, asyncio.TimeoutError):
                pass
        return snapshot["event"]

    try:
        assert asyncio.run(_exercise()) == "session_snapshot"
    finally:
        for item, level in zip(loggers, previous_levels, strict=True):
            item.removeHandler(handler)
            item.setLevel(level)

    combined = "\n".join(captured)
    assert token not in combined
    assert "token=" not in combined
    assert 'WebSocket /ws/chat/chat_logs"' in combined or "WebSocket /ws/chat/chat_logs " in combined
    assert "Accepted chat socket session_id=chat_logs" in combined
    assert combined.count("Rejected chat socket before any chat event") >= 2
    assert get_chat_hub().get_session("chat_logs_missing") is None
    assert get_chat_hub().get_session("chat_logs_bad") is None


def test_auth_frame_snapshot_uses_session_id_as_thread_id(
    chat_server: _ChatServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _install_fake_agent(monkeypatch, {"block_first": False})
    token = _staff_token("staff.one@example.com")

    async def _run() -> list[dict[str, Any]]:
        async with _StaffSocket(chat_server, "chat_0076", token) as connection:
            snapshot = await _recv_json(connection)
            await connection.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": "chat_0076", "text": _FIRST_QUESTION},
                    }
                )
            )
            follow = await _collect_until(connection, "generation_completed")
            return [snapshot, *follow]

    events = asyncio.run(_run())
    assert events[0]["event"] == "session_snapshot"
    assert events[0]["data"]["session_id"] == "chat_0076"
    assert events[0]["data"]["messages"] == []
    names = [item["event"] for item in events]
    assert names[1] == "user_message"
    assert "token_chunk" in names
    assert names.index("token_chunk") < names.index("generation_completed")
    chunk = next(item for item in events if item["event"] == "token_chunk")
    assert chunk["data"]["session_id"] == "chat_0076"
    assert chunk["data"]["sequence"] == 1
    assert isinstance(chunk["data"]["token"], str)
    completed = events[-1]
    assert completed["data"]["session_id"] == "chat_0076"
    assert completed["data"]["message_id"].startswith("msg_")
    session = get_chat_hub().get_session("chat_0076")
    assert session is not None
    assert session.thread_id == "chat_0076"
    assert session.bound_thread_id == "chat_0076"
    assert session.agent_id == "compliance_assistant"
    assert script["calls"][0]["thread_id"] == "chat_0076"
    assert get_chat_hub().generation_starts["chat_0076"] == 1
    # Mocked ordering only: the stand-in returns before a real sample finishes.
    assert session.last_generation["replayed_kept_attempt"] is False


def test_interrupt_keeps_the_partial_and_starts_a_new_turn(
    chat_server: _ChatServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _install_fake_agent(monkeypatch, {"block_first": True})
    token = _staff_token("staff.two@example.com")

    async def _run() -> list[dict[str, Any]]:
        async with _StaffSocket(chat_server, "chat_interrupt", token) as connection:
            assert (await _recv_json(connection))["event"] == "session_snapshot"
            await connection.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": "chat_interrupt", "text": _FIRST_QUESTION},
                    }
                )
            )
            first = await _collect_until(connection, "token_chunk")
            assert script["first_token"].wait(5)
            await connection.send(
                json.dumps(
                    {
                        "event": "interrupt_requested",
                        "data": {"session_id": "chat_interrupt", "new_input": _NEW_INPUT},
                    }
                )
            )
            deadline = time.time() + 5
            while time.time() < deadline:
                active = get_chat_hub().active_watch("chat_interrupt")
                if active is not None and active.stop:
                    break
                await asyncio.sleep(0.02)
            else:
                raise AssertionError("interrupt was not visible to the generation watch")
            script["release"].set()
            rest = await _collect_until(connection, "generation_completed", timeout=5)
            return [*first, *rest]

    events = asyncio.run(_run())
    names = [item["event"] for item in events]
    interrupted_at = names.index("generation_interrupted")
    next_user = names.index("user_message", interrupted_at)
    between = names[interrupted_at + 1 : next_user]
    assert "token_chunk" not in between
    interrupted = next(item for item in events if item["event"] == "generation_interrupted")
    assert interrupted["data"]["status"] == "interrupted"
    assert interrupted["data"]["message_id"].startswith("msg_")
    session = get_chat_hub().get_session("chat_interrupt")
    assert session is not None
    partial = next(message for message in session.messages if message.status == "interrupted")
    assert partial.text == _PARTIAL
    assert partial.role == "assistant"
    assert script["calls"][1]["question"] == _NEW_INPUT
    conversation = script["calls"][1]["conversation"]
    assert conversation is not None
    assert _FIRST_QUESTION in [content for _role, content in conversation]
    assert _PARTIAL in [content for _role, content in conversation]
    assert get_chat_hub().generation_starts["chat_interrupt"] == 2


def test_two_subscribers_share_one_generation(
    chat_server: _ChatServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_agent(monkeypatch, {"block_first": False})
    token = _staff_token("staff.three@example.com")

    async def _run() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        ready = 0
        ready_lock = asyncio.Lock()
        both_ready = asyncio.Event()

        async def _listen(connection: Any) -> list[dict[str, Any]]:
            nonlocal ready
            snapshot = await _recv_json(connection)
            async with ready_lock:
                ready += 1
                if ready == 2:
                    both_ready.set()
            follow = await _collect_until(connection, "generation_completed")
            return [snapshot, *follow]

        async with _StaffSocket(chat_server, "chat_shared", token) as first:
            async with _StaffSocket(chat_server, "chat_shared", token) as second:
                sender = asyncio.create_task(_listen(first))
                watcher = asyncio.create_task(_listen(second))
                await asyncio.wait_for(both_ready.wait(), timeout=5)
                await first.send(
                    json.dumps(
                        {
                            "event": "user_message",
                            "data": {"session_id": "chat_shared", "text": _FIRST_QUESTION},
                        }
                    )
                )
                return await sender, await watcher

    first_events, second_events = asyncio.run(_run())
    assert [item["event"] for item in first_events[1:]] == [item["event"] for item in second_events[1:]]
    assert first_events[1:] == second_events[1:]
    assert get_chat_hub().generation_starts["chat_shared"] == 1


def test_reconnect_snapshot_precedes_the_next_turn(
    chat_server: _ChatServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _install_fake_agent(monkeypatch, {"block_first": False})
    token = _staff_token("staff.four@example.com")

    async def _run() -> dict[str, Any]:
        async with _StaffSocket(chat_server, "chat_restore", token) as connection:
            assert (await _recv_json(connection))["event"] == "session_snapshot"
            await connection.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": "chat_restore", "text": _FIRST_QUESTION},
                    }
                )
            )
            await _collect_until(connection, "generation_completed")
        async with _StaffSocket(chat_server, "chat_restore", token) as restored:
            snapshot = await _recv_json(restored)
            await restored.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": "chat_restore", "text": _NEW_INPUT},
                    }
                )
            )
            follow = await _collect_until(restored, "generation_completed")
            return {"snapshot": snapshot, "follow": follow}

    result = asyncio.run(_run())
    snapshot = result["snapshot"]
    assert snapshot["event"] == "session_snapshot"
    messages = snapshot["data"]["messages"]
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[0]["text"] == _FIRST_QUESTION
    assert messages[1]["text"] == _PARTIAL + _REST
    assert "status" not in messages[1]
    assert result["follow"][0]["event"] == "user_message"
    assert script["calls"][1]["conversation"] is not None
    restored_text = [content for _role, content in script["calls"][1]["conversation"]]
    assert _FIRST_QUESTION in restored_text
    assert _PARTIAL + _REST in restored_text
    assert script["calls"][1]["thread_id"] == "chat_restore"


def test_socket_interrupt_does_not_flush_a_scripted_remainder(
    chat_server: _ChatServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The socket stops a scripted sample without publishing the unsent sentence.

    The model is fake. This checks the worker does not flush buffered releases.
    It does not prove the local GGUF.
    """
    role_chunk = {"choices": [{"delta": {"role": "assistant"}, "finish_reason": None}]}
    finish_chunk = {"choices": [{"delta": {}, "finish_reason": "stop"}]}
    first_sentence = "The indexed referral target is 11 days. "
    second_sentence = "It runs from creation to a confirmed appointment."

    class _ChunkIterator:
        def __init__(self) -> None:
            self._remaining = [
                role_chunk,
                {"choices": [{"delta": {"content": first_sentence}, "finish_reason": None}]},
                {"choices": [{"delta": {"content": second_sentence}, "finish_reason": None}]},
                finish_chunk,
            ]
            self.pulled = 0
            self.closed = False

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

    class _ReferralLlama:
        def __init__(self) -> None:
            self.iterators: list[_ChunkIterator] = []

        def create_chat_completion(self, **_kwargs: Any) -> _ChunkIterator:
            iterator = _ChunkIterator()
            self.iterators.append(iterator)
            return iterator

    fake = _ReferralLlama()
    monkeypatch.setattr("data.pipelines.rag._load_local_llm", lambda: fake)
    monkeypatch.setattr("data.pipelines.rag.GENERATION_API_KEY", "")
    started = threading.Event()
    release = threading.Event()
    from data.pipelines import rag as rag_module

    real_emit = rag_module._emit_kept_release

    def _emit_and_hold(watch: Any, text: str) -> None:
        real_emit(watch, text)
        if not started.is_set():
            started.set()
            release.wait(5)

    monkeypatch.setattr("data.pipelines.rag._emit_kept_release", _emit_and_hold)
    monkeypatch.setattr(
        "data.pipelines.rag.retrieve",
        lambda _question, **_kwargs: [
            {
                "source_document": "referral-process",
                "section": "Target completed-referral time",
                "text": (
                    "Target completed-referral time: 11 days from creation "
                    "to a confirmed appointment."
                ),
            }
        ],
    )
    token = _staff_token("staff.flush@example.com")

    async def _run() -> list[dict[str, Any]]:
        async with _StaffSocket(chat_server, "chat_flush", token) as connection:
            assert (await _recv_json(connection))["event"] == "session_snapshot"
            await connection.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {
                            "session_id": "chat_flush",
                            "text": "How long does an internal referral take?",
                        },
                    }
                )
            )
            first = await _collect_until(connection, "token_chunk")
            assert started.wait(5)
            await connection.send(
                json.dumps(
                    {
                        "event": "interrupt_requested",
                        "data": {"session_id": "chat_flush", "new_input": ""},
                    }
                )
            )
            deadline = time.time() + 5
            while time.time() < deadline:
                active = get_chat_hub().active_watch("chat_flush")
                if active is not None and active.stop:
                    break
                await asyncio.sleep(0.02)
            else:
                raise AssertionError("interrupt was not visible to the generation watch")
            release.set()
            rest = await _collect_until(connection, "generation_interrupted")
            return [*first, *rest]

    events = asyncio.run(_run())
    names = [item["event"] for item in events]
    interrupted_at = names.index("generation_interrupted")
    tokens = [
        item["data"]["token"]
        for index, item in enumerate(events)
        if item["event"] == "token_chunk" and index < interrupted_at
    ]
    assert tokens
    assert "confirmed appointment" not in "".join(tokens)
    assert "token_chunk" not in names[interrupted_at + 1 :]
    assert len(fake.iterators) == 1
    assert fake.iterators[0].closed is True
    session = get_chat_hub().get_session("chat_flush")
    assert session is not None
    assert session.last_generation["replayed_kept_attempt"] is False
    assert "".join(tokens) == session.last_generation["stored_text"]


def test_unpublished_replacement_is_not_the_shared_transcript(
    chat_server: _ChatServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both sockets see the streamed turn. History keeps that text, not the agent return.

    The agent is a stand-in. This does not prove a live grounding retry.
    """
    calls: list[dict[str, Any]] = []

    def _run(question: str, *, thread_id: str | None = None, **_kwargs: Any) -> AgentRun:
        from data.pipelines.rag import _GENERATION_CONVERSATION, _LOCAL_GENERATION_WATCH

        watch = _LOCAL_GENERATION_WATCH.get()
        calls.append(
            {
                "question": question,
                "conversation": _GENERATION_CONVERSATION.get(),
                "thread_id": thread_id,
            }
        )
        if watch is not None and watch.on_kept_release is not None:
            watch.on_kept_release("STREAMED_TURN.")
        return AgentRun(
            answer="UNPUBLISHED_REPLACEMENT.",
            error="",
            trace_id="mock-trace",
            thread_id=thread_id or "",
        )

    monkeypatch.setattr("app.services.chat_channel.run_support_agent", _run)
    token = _staff_token("staff.transcript@example.com")

    async def _collect(connection: Any, ready: asyncio.Event) -> list[dict[str, Any]]:
        assert (await _recv_json(connection))["event"] == "session_snapshot"
        ready.set()
        return await _collect_until(connection, "generation_completed")

    async def _run_socket() -> dict[str, Any]:
        sender_ready = asyncio.Event()
        watcher_ready = asyncio.Event()
        async with _StaffSocket(chat_server, "chat_same_turn", token) as sender:
            async with _StaffSocket(chat_server, "chat_same_turn", token) as watcher:
                sender_task = asyncio.create_task(_collect(sender, sender_ready))
                watcher_task = asyncio.create_task(_collect(watcher, watcher_ready))
                await asyncio.wait_for(sender_ready.wait(), 5)
                await asyncio.wait_for(watcher_ready.wait(), 5)
                await sender.send(
                    json.dumps(
                        {
                            "event": "user_message",
                            "data": {
                                "session_id": "chat_same_turn",
                                "text": "How long does an internal referral take?",
                            },
                        }
                    )
                )
                sender_events, watcher_events = await asyncio.gather(sender_task, watcher_task)
        async with _StaffSocket(chat_server, "chat_same_turn", token) as restored:
            snapshot = await _recv_json(restored)
            await restored.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {
                            "session_id": "chat_same_turn",
                            "text": "What is the indexed referral target?",
                        },
                    }
                )
            )
            await _collect_until(restored, "generation_completed")
        return {"sender": sender_events, "watcher": watcher_events, "snapshot": snapshot}

    result = asyncio.run(_run_socket())
    sender_tokens = [item["data"]["token"] for item in result["sender"] if item["event"] == "token_chunk"]
    watcher_tokens = [item["data"]["token"] for item in result["watcher"] if item["event"] == "token_chunk"]
    assert sender_tokens == watcher_tokens == ["STREAMED_TURN."]
    assert result["sender"] == result["watcher"]
    messages = result["snapshot"]["data"]["messages"]
    assert messages[1]["text"] == "STREAMED_TURN."
    assert "UNPUBLISHED_REPLACEMENT." not in messages[1]["text"]
    assert calls[1]["conversation"] == (
        ("user", "How long does an internal referral take?"),
        ("assistant", "STREAMED_TURN."),
    )
    session = get_chat_hub().get_session("chat_same_turn")
    assert session is not None
    assert session.messages[1].text == "STREAMED_TURN."
    assert session.last_generation["unpublished_agent_answer"] == "UNPUBLISHED_REPLACEMENT."


def test_retry_context_overflow_finishes_the_published_turn_for_every_subscriber(
    chat_server: _ChatServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retry that cannot fit the context window still ends the streamed turn.

    The model is scripted. The second sample raises the local sampler's
    context-window error after the first sample has been published. A later
    question still completes. This does not prove the live GGUF.
    """
    published = "The indexed referral target is 11 days."
    follow_up = "The indexed referral target is recorded separately."
    scripts = [[published], [follow_up]]

    class _OverflowOnRetry:
        def __init__(self) -> None:
            self.calls = 0
            self._inner = None

        def create_chat_completion(self, **kwargs: Any) -> Any:
            self.calls += 1
            if self.calls == 2:
                raise ValueError("Requested tokens (2086) exceed context window of 2048")
            from tests.pipelines.test_gated_generation_stream import _ScriptedLlama

            if self._inner is None:
                self._inner = _ScriptedLlama(scripts)
            return self._inner.create_chat_completion(**kwargs)

    fake = _OverflowOnRetry()
    monkeypatch.setattr("data.pipelines.rag._load_local_llm", lambda: fake)
    monkeypatch.setattr("data.pipelines.rag.GENERATION_API_KEY", "")

    def _run(question: str, *, thread_id: str | None = None, **_kwargs: Any) -> AgentRun:
        from data.pipelines.rag import generate_answer

        answer = generate_answer(
            question,
            [{"source_document": "referral-process", "text": follow_up}],
        )
        return AgentRun(answer=answer, error="", trace_id="overflow", thread_id=thread_id or "")

    monkeypatch.setattr("app.services.chat_channel.run_support_agent", _run)
    token = _staff_token("staff.overflow@example.com")

    async def _collect(connection: Any, ready: asyncio.Event) -> list[dict[str, Any]]:
        assert (await _recv_json(connection))["event"] == "session_snapshot"
        ready.set()
        return await _collect_until(connection, "generation_completed")

    async def _run_socket() -> dict[str, Any]:
        sender_ready = asyncio.Event()
        watcher_ready = asyncio.Event()
        async with _StaffSocket(chat_server, "chat_overflow", token) as sender:
            async with _StaffSocket(chat_server, "chat_overflow", token) as watcher:
                sender_task = asyncio.create_task(_collect(sender, sender_ready))
                watcher_task = asyncio.create_task(_collect(watcher, watcher_ready))
                await asyncio.wait_for(sender_ready.wait(), 5)
                await asyncio.wait_for(watcher_ready.wait(), 5)
                await sender.send(
                    json.dumps(
                        {
                            "event": "user_message",
                            "data": {
                                "session_id": "chat_overflow",
                                "text": "What is the indexed referral target?",
                            },
                        }
                    )
                )
                sender_events, watcher_events = await asyncio.gather(sender_task, watcher_task)
        async with _StaffSocket(chat_server, "chat_overflow", token) as restored:
            snapshot = await _recv_json(restored)
            await restored.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {
                            "session_id": "chat_overflow",
                            "text": "What is recorded for the indexed referral target?",
                        },
                    }
                )
            )
            follow_events = await _collect_until(restored, "generation_completed")
        return {
            "sender": sender_events,
            "watcher": watcher_events,
            "snapshot": snapshot,
            "follow": follow_events,
        }

    result = asyncio.run(_run_socket())
    sender_tokens = [item["data"]["token"] for item in result["sender"] if item["event"] == "token_chunk"]
    watcher_tokens = [item["data"]["token"] for item in result["watcher"] if item["event"] == "token_chunk"]
    assert "".join(sender_tokens) == published
    assert sender_tokens == watcher_tokens
    assert result["sender"][-1]["event"] == "generation_completed"
    assert result["watcher"][-1]["event"] == "generation_completed"
    messages = result["snapshot"]["data"]["messages"]
    assert messages[1]["text"] == published
    assert messages[1].get("status") != "interrupted"
    follow_tokens = "".join(
        item["data"]["token"] for item in result["follow"] if item["event"] == "token_chunk"
    )
    assert follow_tokens == follow_up
    assert result["follow"][-1]["event"] == "generation_completed"
    session = get_chat_hub().get_session("chat_overflow")
    assert session is not None
    assert session.messages[1].text == published
    assert session.messages[1].status == "completed"
    assert "unpublished_agent_answer" not in session.last_generation
    assert session.messages[3].text == follow_up
    assert session.messages[3].status == "completed"
    restored_prompt = session.last_generation["attempts"][-1]["prompt_messages"]
    prompt_text = " ".join(item["content"] for item in restored_prompt)
    assert published in prompt_text


def test_first_sample_context_overflow_does_not_complete_the_turn(
    chat_server: _ChatServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A first sample that cannot fit the context window is not marked completed."""

    class _FailFirst:
        def create_chat_completion(self, **_kwargs: Any) -> Any:
            raise ValueError("Requested tokens (2086) exceed context window of 2048")

    monkeypatch.setattr("data.pipelines.rag._load_local_llm", lambda: _FailFirst())
    monkeypatch.setattr("data.pipelines.rag.GENERATION_API_KEY", "")

    def _run(question: str, *, thread_id: str | None = None, **_kwargs: Any) -> AgentRun:
        from data.pipelines.rag import generate_answer

        answer = generate_answer(
            question,
            [{"source_document": "referral-process", "text": "The indexed referral target is recorded separately."}],
        )
        return AgentRun(answer=answer, error="", trace_id="first-overflow", thread_id=thread_id or "")

    monkeypatch.setattr("app.services.chat_channel.run_support_agent", _run)
    token = _staff_token("staff.firstoverflow@example.com")

    async def _run_socket() -> str:
        async with _StaffSocket(chat_server, "chat_first_overflow", token) as connection:
            assert (await _recv_json(connection))["event"] == "session_snapshot"
            await connection.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {
                            "session_id": "chat_first_overflow",
                            "text": "What is the indexed referral target?",
                        },
                    }
                )
            )
            echoed = await _recv_json(connection)
            assert echoed["event"] == "user_message"
            try:
                unexpected = await _recv_json(connection, timeout=0.4)
            except (TimeoutError, asyncio.TimeoutError):
                return ""
            return str(unexpected.get("event"))

    assert asyncio.run(_run_socket()) == ""
    session = get_chat_hub().get_session("chat_first_overflow")
    assert session is not None
    assert session.generating is False
    assert session.messages[-1].role == "assistant"
    assert session.messages[-1].text == ""
    assert session.messages[-1].status == "in_progress"


def test_a_second_user_cannot_read_the_session(chat_server: _ChatServer) -> None:
    owner = _staff_token("owner.staff@example.com")
    other = _staff_token("other.staff@example.com")

    async def _run() -> list[dict[str, Any]]:
        async with _StaffSocket(chat_server, "chat_owned", owner):
            received: list[dict[str, Any]] = []
            try:
                async with _StaffSocket(chat_server, "chat_owned", other) as intruder:
                    received.append(await _recv_json(intruder, timeout=2))
            except (ConnectionClosed, TimeoutError, asyncio.TimeoutError):
                return received
            return received

    assert asyncio.run(_run()) == []
