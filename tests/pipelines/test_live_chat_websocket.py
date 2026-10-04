"""Live WebSocket evidence with the local GGUF.

Skipped unless PART2_LIVE_CHAT_WS=1. The contract tests use a stand-in agent
and do not prove this file's claims.

Retrieval is patched because the local Qdrant index is not present. Generation,
the release gate, the socket, and cancellation use the real path. This does
not prove that retrieval ran.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest
import uvicorn
import websockets
from fastapi import FastAPI

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.db.database import reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.routers.chat import router  # noqa: E402
from app.schemas.user import UserCreate, UserRole  # noqa: E402
from app.services import user_service  # noqa: E402
from app.services.chat_channel import get_chat_hub, reset_chat_hub_for_tests  # noqa: E402
from data.pipelines.rag import local_llm_is_loaded, release_local_llm  # noqa: E402
from shared.healthcore_rag.config import (  # noqa: E402
    GENERATION_API_KEY,
    LOCAL_GENERATION_GGUF_FILENAME,
    MODELS_DIR,
)

LIVE_ENV = "PART2_LIVE_CHAT_WS"
_SESSION_ID = "chat_live_ws"
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
_NEW_INPUT = "What does the minimum necessary standard require for a covered entity?"


def _live_requested() -> bool:
    return os.getenv(LIVE_ENV, "").strip() == "1"


def _compliance_chunk(_question: str, **_kwargs: object) -> list[dict[str, str]]:
    """Stand in for the missing Qdrant index. This is not a retrieval result."""
    return [
        {
            "source_document": "compliance-reference",
            "section": "US clinics: HIPAA permitted uses and disclosures",
            "text": _COMPLIANCE_CONTEXT,
        }
    ]


@pytest.fixture
def live_chat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "incidents.json"))
    monkeypatch.setenv("SECRET_KEY", "isolated-live-chat-secret-key-32b")
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
    monkeypatch.setattr("data.pipelines.rag.retrieve", _compliance_chunk)
    port_probe = socket.socket()
    port_probe.bind(("127.0.0.1", 0))
    port = int(port_probe.getsockname()[1])
    port_probe.close()
    application = FastAPI()
    application.include_router(router)
    server = uvicorn.Server(
        uvicorn.Config(application, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        server.should_exit = True
        raise RuntimeError("live chat server did not start")
    try:
        yield port
    finally:
        server.should_exit = True
        thread.join(5)
        release_local_llm()
        reset_chat_hub_for_tests()
        reset_db_for_tests()
        reset_engine_for_tests()
        get_settings.cache_clear()


def _chat_url(port: int, session_id: str) -> str:
    """Socket URL with no credential. Authentication is the first auth frame."""
    return f"ws://127.0.0.1:{port}/ws/chat/{session_id}"


def _auth_frame(token: str) -> str:
    return json.dumps({"event": "auth", "data": {"token": token}})


async def _recv_json(connection: Any, timeout: float) -> dict[str, Any]:
    raw = await asyncio.wait_for(connection.recv(), timeout)
    payload = json.loads(raw)
    assert isinstance(payload, dict)
    return payload


@pytest.mark.skipif(not _live_requested(), reason=f"Set {LIVE_ENV}=1 for the live chat socket")
def test_live_socket_streams_and_interrupt_stops_the_model(live_chat: int) -> None:
    if GENERATION_API_KEY:
        pytest.fail("GENERATION_API_KEY is set, so generation would not use the local GGUF.")
    model_file = MODELS_DIR / LOCAL_GENERATION_GGUF_FILENAME
    if not model_file.is_file() or model_file.stat().st_size <= 0:
        pytest.fail(f"Local GGUF is missing: {model_file}")

    user = user_service.create_user(
        UserCreate(email="live.staff@example.com", password="test-password-1"),
        role=UserRole.manager,
    )
    token = create_access_token(subject=user.id)
    url = _chat_url(live_chat, _SESSION_ID)

    async def _run() -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        first_report: dict[str, Any] = {}
        async with websockets.connect(url) as connection:
            await connection.send(_auth_frame(token))
            snapshot = await _recv_json(connection, 10)
            await connection.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": _SESSION_ID, "text": _QUESTION},
                    }
                )
            )
            deadline = time.time() + 180
            while time.time() < deadline:
                events.append(await _recv_json(connection, deadline - time.time()))
                if events[-1]["event"] == "token_chunk":
                    break
                if events[-1]["event"] == "generation_completed":
                    break
            await connection.send(
                json.dumps(
                    {
                        "event": "interrupt_requested",
                        "data": {"session_id": _SESSION_ID, "new_input": ""},
                    }
                )
            )
            terminal = time.time() + 60
            while time.time() < terminal:
                events.append(await _recv_json(connection, terminal - time.time()))
                if events[-1]["event"] == "generation_interrupted":
                    session = get_chat_hub().get_session(_SESSION_ID)
                    if session is not None:
                        first_report = dict(session.last_generation)
                    break
        async with websockets.connect(url) as restored:
            await restored.send(_auth_frame(token))
            restored_snapshot = await _recv_json(restored, 10)
            await restored.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": _SESSION_ID, "text": _NEW_INPUT},
                    }
                )
            )
            prompt_deadline = time.time() + 60
            second_prompt: list[dict[str, str]] = []
            while time.time() < prompt_deadline:
                watch = get_chat_hub().active_watch(_SESSION_ID)
                if watch is not None and watch.observations:
                    second_prompt = watch.observations[-1].prompt_messages
                    blob = "\n".join(item.get("content", "") for item in second_prompt)
                    session = get_chat_hub().get_session(_SESSION_ID)
                    partial = ""
                    if session is not None:
                        interrupted_messages = [
                            message.text
                            for message in session.messages
                            if message.status == "interrupted"
                        ]
                        partial = interrupted_messages[-1] if interrupted_messages else ""
                    if _QUESTION in blob and _NEW_INPUT in blob and partial and partial in blob:
                        break
                await asyncio.sleep(0.05)
            await restored.send(
                json.dumps(
                    {
                        "event": "interrupt_requested",
                        "data": {"session_id": _SESSION_ID, "new_input": ""},
                    }
                )
            )
            stop_deadline = time.time() + 60
            while time.time() < stop_deadline:
                watch = get_chat_hub().active_watch(_SESSION_ID)
                if watch is None:
                    break
                await asyncio.sleep(0.05)
            return {
                "snapshot": snapshot,
                "events": events,
                "restored_snapshot": restored_snapshot,
                "second_prompt": second_prompt,
                "first_report": first_report,
            }

    result = asyncio.run(_run())
    names = [item["event"] for item in result["events"]]
    print(
        "LIVE_CHAT",
        {
            "snapshot": result["snapshot"]["event"],
            "events": names,
            "loaded_after": local_llm_is_loaded(),
        },
    )
    assert result["snapshot"]["event"] == "session_snapshot"
    assert result["snapshot"]["data"]["messages"] == []
    assert "token_chunk" in names
    token_at = names.index("token_chunk")
    assert "generation_completed" not in names[: token_at + 1]
    interrupted_at = names.index("generation_interrupted")
    assert token_at < interrupted_at
    assert "token_chunk" not in names[interrupted_at + 1 :]
    restored = result["restored_snapshot"]
    assert restored["event"] == "session_snapshot"
    restored_messages = restored["data"]["messages"]
    assert restored_messages[0]["role"] == "user"
    assert restored_messages[0]["text"] == _QUESTION
    assert restored_messages[1]["role"] == "assistant"
    assert restored_messages[1]["status"] == "interrupted"

    session = get_chat_hub().get_session(_SESSION_ID)
    assert session is not None
    assert session.thread_id == _SESSION_ID
    assert session.bound_thread_id == _SESSION_ID
    partials = [message for message in session.messages if message.status == "interrupted"]
    assert partials
    assert partials[0].text
    assert partials[0].role == "assistant"
    report = result["first_report"]
    attempts = report["attempts"]
    print(
        "LIVE_CHAT_GENERATION",
        {
            "kept_attempt_index": report["kept_attempt_index"],
            "replayed_kept_attempt": report["replayed_kept_attempt"],
            "replaced_kept_text": report["replaced_kept_text"],
            "discarded_chars": len(report["discarded_attempt_text"]),
            "published_chars": len(report["published_text"]),
            "stored_chars": len(report["stored_text"]),
            "attempts": [
                {
                    "chunks_after_release": item["content_chunks_after_first_release"],
                    "interrupted": item["interrupted"],
                    "closed": item["iterator_closed"],
                    "finish_reason": item["finish_reason"],
                    "releases": item["release_count"],
                }
                for item in attempts
            ],
        },
    )
    assert report["replayed_kept_attempt"] is False
    assert report["interrupted"] is True
    kept = attempts[report["kept_attempt_index"]]
    assert kept["interrupted"] is True
    assert kept["iterator_closed"] is True
    assert kept["finish_reason"] is None
    assert kept["published_before_iterator_close"] is True
    first_turn_tokens = []
    seen_interrupt = False
    for item in result["events"]:
        if item["event"] == "generation_interrupted":
            seen_interrupt = True
        elif item["event"] == "token_chunk" and not seen_interrupt:
            first_turn_tokens.append(item["data"]["token"])
    published = "".join(first_turn_tokens)
    assert published == partials[0].text
    assert len(first_turn_tokens) == kept["release_count"]
    if kept["withheld_text"]:
        assert kept["withheld_text"] not in published
    if report["discarded_attempt_text"]:
        assert not published.startswith(report["discarded_attempt_text"])
    prompt_blob = "\n".join(item.get("content", "") for item in result["second_prompt"])
    assert _QUESTION in prompt_blob
    assert partials[0].text in prompt_blob
    assert _NEW_INPUT in prompt_blob
    assert session.thread_id == _SESSION_ID


_REFERRAL_CONTEXT = (
    "Target completed-referral time: 11 days from creation to a confirmed appointment."
)
_REFERRAL_QUESTION = "How long does an internal referral take?"


def _referral_chunk(_question: str, **_kwargs: object) -> list[dict[str, str]]:
    """Stand in for the missing Qdrant index. This is not a retrieval result."""
    return [
        {
            "source_document": "referral-process",
            "section": "Target completed-referral time",
            "text": _REFERRAL_CONTEXT,
        }
    ]


@pytest.mark.skipif(not _live_requested(), reason=f"Set {LIVE_ENV}=1 for the live no-retry socket")
def test_live_no_retry_streams_before_the_iterator_finishes(
    live_chat: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completion and interrupt for a question that is not steered into a retry.

    Retrieval is still patched because the Qdrant index is absent. If this
    question retries, the test fails instead of disabling the retry.
    """
    if GENERATION_API_KEY:
        pytest.fail("GENERATION_API_KEY is set, so generation would not use the local GGUF.")
    model_file = MODELS_DIR / LOCAL_GENERATION_GGUF_FILENAME
    if not model_file.is_file() or model_file.stat().st_size <= 0:
        pytest.fail(f"Local GGUF is missing: {model_file}")
    monkeypatch.setattr("data.pipelines.rag.retrieve", _referral_chunk)

    user = user_service.create_user(
        UserCreate(email="noretry.staff@example.com", password="test-password-1"),
        role=UserRole.manager,
    )
    token = create_access_token(subject=user.id)

    async def _until(connection: Any, terminal_event: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        deadline = time.time() + 180
        while time.time() < deadline:
            events.append(await _recv_json(connection, deadline - time.time()))
            if events[-1]["event"] == terminal_event:
                return events
        raise AssertionError(f"did not receive {terminal_event}")

    async def _run() -> dict[str, Any]:
        done_url = _chat_url(live_chat, "chat_noretry_done")
        stop_url = _chat_url(live_chat, "chat_noretry_stop")
        async with websockets.connect(done_url) as connection:
            await connection.send(_auth_frame(token))
            assert (await _recv_json(connection, 10))["event"] == "session_snapshot"
            await connection.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": "chat_noretry_done", "text": _REFERRAL_QUESTION},
                    }
                )
            )
            completed_events = await _until(connection, "generation_completed")
        async with websockets.connect(stop_url) as connection:
            await connection.send(_auth_frame(token))
            assert (await _recv_json(connection, 10))["event"] == "session_snapshot"
            await connection.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": "chat_noretry_stop", "text": _REFERRAL_QUESTION},
                    }
                )
            )
            first = await _until(connection, "token_chunk")
            await connection.send(
                json.dumps(
                    {
                        "event": "interrupt_requested",
                        "data": {"session_id": "chat_noretry_stop", "new_input": ""},
                    }
                )
            )
            stopped = await _until(connection, "generation_interrupted")
        return {"completed": completed_events, "stopped": [*first, *stopped]}

    result = asyncio.run(_run())
    done = get_chat_hub().get_session("chat_noretry_done")
    stopped = get_chat_hub().get_session("chat_noretry_stop")
    assert done is not None and stopped is not None
    done_report = done.last_generation
    stop_report = stopped.last_generation
    done_names = [item["event"] for item in result["completed"]]
    stop_names = [item["event"] for item in result["stopped"]]
    print(
        "LIVE_NO_RETRY",
        {
            "completed_events": done_names,
            "attempts": len(done_report["attempts"]),
            "chunks_after_release": done_report["attempts"][0]["content_chunks_after_first_release"],
            "published_before_close": done_report["attempts"][0]["published_before_iterator_close"],
            "finish_reason": done_report["attempts"][0]["finish_reason"],
            "replacement_unpublished": done_report["replacement_unpublished"],
            "replayed": done_report["replayed_kept_attempt"],
            "stopped_events": stop_names,
            "stopped_releases": stop_report["attempts"][-1]["release_count"],
            "stopped_withheld_chars": len(stop_report["attempts"][-1]["withheld_text"]),
        },
    )
    assert len(done_report["attempts"]) == 1
    assert done_report["replacement_unpublished"] is False
    assert done_report["replayed_kept_attempt"] is False
    attempt = done_report["attempts"][0]
    assert attempt["published_before_iterator_close"] is True
    assert attempt["content_chunks_after_first_release"] > 0
    assert attempt["finish_reason"] == "stop"
    assert attempt["interrupted"] is False
    assert done_names.index("token_chunk") < done_names.index("generation_completed")
    completed_tokens = "".join(
        item["data"]["token"] for item in result["completed"] if item["event"] == "token_chunk"
    )
    assert completed_tokens == done_report["stored_text"]
    assert completed_tokens == done_report["published_text"]

    interrupted_at = stop_names.index("generation_interrupted")
    assert stop_names.index("token_chunk") < interrupted_at
    assert "token_chunk" not in stop_names[interrupted_at + 1 :]
    assert len(stop_report["attempts"]) == 1
    stopped_attempt = stop_report["attempts"][0]
    assert stopped_attempt["interrupted"] is True
    assert stopped_attempt["finish_reason"] is None
    assert stopped_attempt["published_before_iterator_close"] is True
    stopped_tokens = []
    for index, item in enumerate(result["stopped"]):
        if item["event"] == "token_chunk" and index < interrupted_at:
            stopped_tokens.append(item["data"]["token"])
    assert "".join(stopped_tokens) == stop_report["published_text"]
    assert "".join(stopped_tokens) == stop_report["stored_text"]
    assert len(stopped_tokens) == stopped_attempt["release_count"]
    if stopped_attempt["withheld_text"]:
        assert stopped_attempt["withheld_text"] not in "".join(stopped_tokens)


@pytest.mark.skipif(not _live_requested(), reason=f"Set {LIVE_ENV}=1 for the live retry publication check")
def test_live_retry_is_not_concatenated_onto_the_streamed_attempt(live_chat: int) -> None:
    """Let the compliance question finish. It retries on its own.

    Both subscribers see the first sample. The transcript, the reconnect
    snapshot, and the next turn's conversation keep that text. The unpublished
    replacement is not written over it. Retrieval is patched because the
    Qdrant index is absent.
    """
    if GENERATION_API_KEY:
        pytest.fail("GENERATION_API_KEY is set, so generation would not use the local GGUF.")
    model_file = MODELS_DIR / LOCAL_GENERATION_GGUF_FILENAME
    if not model_file.is_file():
        pytest.fail(f"Local GGUF is missing: {model_file}")
    user = user_service.create_user(
        UserCreate(email="retry.staff@example.com", password="test-password-1"),
        role=UserRole.manager,
    )
    token = create_access_token(subject=user.id)
    url = _chat_url(live_chat, "chat_live_retry")
    follow_up = "What does the minimum necessary standard require for a covered entity?"

    async def _collect(connection: Any, ready: asyncio.Event) -> list[dict[str, Any]]:
        assert (await _recv_json(connection, 10))["event"] == "session_snapshot"
        ready.set()
        events: list[dict[str, Any]] = []
        deadline = time.time() + 180
        while time.time() < deadline:
            events.append(await _recv_json(connection, max(deadline - time.time(), 1)))
            if events[-1]["event"] in {"generation_completed", "generation_interrupted"}:
                return events
        raise AssertionError("generation did not finish")

    async def _run() -> dict[str, Any]:
        sender_ready = asyncio.Event()
        watcher_ready = asyncio.Event()
        async with websockets.connect(url) as sender, websockets.connect(url) as watcher:
            await sender.send(_auth_frame(token))
            await watcher.send(_auth_frame(token))
            sender_task = asyncio.create_task(_collect(sender, sender_ready))
            watcher_task = asyncio.create_task(_collect(watcher, watcher_ready))
            await asyncio.wait_for(sender_ready.wait(), 10)
            await asyncio.wait_for(watcher_ready.wait(), 10)
            await sender.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": "chat_live_retry", "text": _QUESTION},
                    }
                )
            )
            sender_events, watcher_events = await asyncio.gather(sender_task, watcher_task)
        finished = get_chat_hub().get_session("chat_live_retry")
        assert finished is not None
        first_report = dict(finished.last_generation)
        async with websockets.connect(url) as restored:
            await restored.send(_auth_frame(token))
            snapshot = await _recv_json(restored, 10)
            await restored.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": "chat_live_retry", "text": follow_up},
                    }
                )
            )
            prompt: list[dict[str, str]] = []
            deadline = time.time() + 60
            while time.time() < deadline:
                watch = get_chat_hub().active_watch("chat_live_retry")
                if watch is not None and watch.observations:
                    prompt = watch.observations[-1].prompt_messages
                    blob = "\n".join(item.get("content", "") for item in prompt)
                    if follow_up in blob and _QUESTION in blob:
                        break
                await asyncio.sleep(0.05)
            await restored.send(
                json.dumps(
                    {
                        "event": "interrupt_requested",
                        "data": {"session_id": "chat_live_retry", "new_input": ""},
                    }
                )
            )
            stop_deadline = time.time() + 60
            while time.time() < stop_deadline:
                if get_chat_hub().active_watch("chat_live_retry") is None:
                    break
                await asyncio.sleep(0.05)
        return {
            "sender": sender_events,
            "watcher": watcher_events,
            "snapshot": snapshot,
            "prompt": prompt,
            "first_report": first_report,
        }

    result = asyncio.run(_run())
    events = result["sender"]
    report = result["first_report"]
    names = [item["event"] for item in events]
    tokens = [item["data"]["token"] for item in events if item["event"] == "token_chunk"]
    print(
        "LIVE_RETRY",
        {
            "events": names,
            "attempts": len(report["attempts"]),
            "token_count": len(tokens),
            "first_releases": report["attempts"][0]["release_count"] if report["attempts"] else 0,
            "second_releases": report["attempts"][1]["release_count"] if len(report["attempts"]) > 1 else 0,
            "first_chunks_after": report["attempts"][0]["content_chunks_after_first_release"] if report["attempts"] else 0,
            "first_published_before_close": report["attempts"][0]["published_before_iterator_close"] if report["attempts"] else False,
            "second_published_before_close": report["attempts"][1]["published_before_iterator_close"] if len(report["attempts"]) > 1 else None,
            "replacement_unpublished": report["replacement_unpublished"],
            "replaced_kept_text": report["replaced_kept_text"],
            "published_chars": len(report["published_text"]),
            "stored_chars": len(report["stored_text"]),
            "discarded_chars": len(report["discarded_attempt_text"]),
        },
    )
    assert names[-1] == "generation_completed"
    assert names.index("token_chunk") < names.index("generation_completed")
    assert set(names).issubset({"user_message", "token_chunk", "generation_completed"})
    assert len(report["attempts"]) == 2
    first, second = report["attempts"]
    assert first["published_before_iterator_close"] is True
    assert first["content_chunks_after_first_release"] > 0
    assert first["finish_reason"] == "stop"
    assert second["published_before_iterator_close"] is False
    assert second["release_count"] > 0
    assert report["replacement_unpublished"] is True
    assert report["replaced_kept_text"] is True
    assert report["replayed_kept_attempt"] is False
    streamed = "".join(tokens)
    watcher_tokens = [
        item["data"]["token"] for item in result["watcher"] if item["event"] == "token_chunk"
    ]
    unpublished = report.get("unpublished_agent_answer", "")
    snapshot_messages = result["snapshot"]["data"]["messages"]
    assistant_history = [
        item["content"] for item in result["prompt"] if item.get("role") == "assistant"
    ]
    print(
        "LIVE_RETRY_HISTORY",
        {
            "subscribers_match": tokens == watcher_tokens,
            "stored_equals_stream": report["stored_text"] == streamed,
            "unpublished_chars": len(unpublished),
            "snapshot_chars": len(snapshot_messages[1]["text"]) if len(snapshot_messages) > 1 else 0,
            "next_turn_matches_stream": streamed in assistant_history,
        },
    )
    assert tokens == watcher_tokens
    assert streamed == report["published_text"]
    assert len(tokens) == first["release_count"]
    assert report["stored_text"] == streamed
    assert unpublished
    assert unpublished != streamed
    assert result["snapshot"]["event"] == "session_snapshot"
    assert snapshot_messages[1]["role"] == "assistant"
    assert snapshot_messages[1]["text"] == streamed
    assert "status" not in snapshot_messages[1]
    assert streamed in assistant_history
    assert unpublished not in assistant_history


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT), str(API_ROOT)])
    env.pop("GENERATION_API_KEY", None)
    return env


def _run_child(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=_child_env(),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


@pytest.mark.skipif(not _live_requested(), reason=f"Set {LIVE_ENV}=1 for the model lifecycle check")
def test_explicit_llama_close_succeeds_and_unchecked_del_does_not() -> None:
    """Compare process exit with the shutdown order that raises in ``free_model``.

    A short process that only loads the model and exits can still call
    ``llama_model_free`` successfully, because ``Llama.__del__`` runs before
    ``llama_cpp`` has been cleared. The reported ``TypeError`` happens when
    ``llama_model_free`` is already None, which is the interpreter-shutdown
    order. ``release_local_llm`` closes the model while that pointer still
    works. A later ``close`` does not call it again.
    """
    if GENERATION_API_KEY:
        pytest.fail("GENERATION_API_KEY is set, so the local model would not load.")
    model_file = MODELS_DIR / LOCAL_GENERATION_GGUF_FILENAME
    if not model_file.is_file():
        pytest.fail(f"Local GGUF is missing: {model_file}")

    plain_exit = _run_child("from data.pipelines.rag import _load_local_llm\n_load_local_llm()\n")
    pointer_cleared = _run_child(
        "\n".join(
            [
                "import data.pipelines.rag as rag",
                "import llama_cpp.llama_cpp as llama_lib",
                "model = rag._load_local_llm()",
                "rag._local_llm = None",
                "llama_lib.llama_model_free = None",
                "try:",
                "    model.close()",
                "    print('UNEXPECTED_CLEAN')",
                "except TypeError as exc:",
                "    print('DEL_TYPEERROR', exc)",
            ]
        )
    )
    released_first = _run_child(
        "\n".join(
            [
                "import data.pipelines.rag as rag",
                "import llama_cpp.llama_cpp as llama_lib",
                "model = rag._load_local_llm()",
                "assert rag.release_local_llm() is True",
                "assert rag.local_llm_is_loaded() is False",
                "llama_lib.llama_model_free = None",
                "model.close()",
                "print('SECOND_CLOSE_OK')",
            ]
        )
    )
    print(
        "LLAMA_LIFECYCLE",
        {
            "plain_exit": plain_exit.returncode,
            "plain_stderr_has_typeerror": "TypeError" in plain_exit.stderr,
            "cleared_exit": pointer_cleared.returncode,
            "cleared_stdout": pointer_cleared.stdout.strip(),
            "released_exit": released_first.returncode,
            "released_stdout": released_first.stdout.strip(),
            "released_stderr_has_typeerror": "TypeError" in released_first.stderr,
        },
    )
    assert plain_exit.returncode == 0
    assert "DEL_TYPEERROR" in pointer_cleared.stdout
    assert "NoneType" in pointer_cleared.stdout
    assert released_first.returncode == 0
    assert "SECOND_CLOSE_OK" in released_first.stdout
    assert "TypeError" not in released_first.stderr
