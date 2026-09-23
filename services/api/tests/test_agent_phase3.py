"""Phase 3 routing, timeout, and authorization checks.

Timeout sleeps are allowed to replace the incident read. Success lookups in
this file call the real incident service. Retrieval and generation are
patched so these tests stay asset-independent whether or not a local Qdrant
index and GGUF happen to be present.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.agent.graph import run_support_agent  # noqa: E402
from app.agent.lookup_slot import (  # noqa: E402
    INCIDENT_LOOKUP_TIMEOUT_SECONDS,
    handoff_count,
    in_flight_count,
    run_bounded_read,
    worker_is_daemon,
)
from app.agent.routing import HONEST_STATUS_SENTENCE, classify_question  # noqa: E402
from app.agent.tracing import load_trace  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.db.database import reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.routers.agent import router  # noqa: E402
from app.schemas.incident import IncidentCreate  # noqa: E402
from app.schemas.user import UserCreate  # noqa: E402
from app.services import incident_service, user_service  # noqa: E402

STATUS_WORDS = ("open", "in_progress", "resolved", "discarded")
SEEDED_TITLE = "SEED_TITLE_ZX9"
SEEDED_DESCRIPTION = "SEED_DESC_ZX9"
RAG_ANSWER = "The indexed policy says 11 days."


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "checkpoints" / "support_agent.sqlite", tmp_path / "traces"


def _patch_rag(monkeypatch: pytest.MonkeyPatch, answer: str = RAG_ANSWER) -> dict[str, int]:
    calls = {"retrieve": 0, "generate": 0}

    def retrieve(_query: str, **_kwargs: object) -> list[dict[str, str]]:
        calls["retrieve"] += 1
        return [{"source_document": "referral-process", "text": "11 days"}]

    def generate(_question: str, _context: list[dict[str, str]]) -> str:
        calls["generate"] += 1
        return answer

    monkeypatch.setattr("data.pipelines.rag.retrieve", retrieve)
    monkeypatch.setattr("data.pipelines.rag.generate_answer", generate)
    return calls


def _run(tmp_path: Path, question: str, *, authenticated: bool) -> tuple[Any, dict[str, Any]]:
    database_path, trace_dir = _paths(tmp_path)
    outcome = run_support_agent(
        question,
        caller_is_authenticated=authenticated,
        checkpoint_path=database_path,
        trace_dir=trace_dir,
    )
    return outcome, load_trace(outcome.trace_id, trace_dir)


@pytest.fixture
def isolated_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TINYDB_PATH", str(tmp_path / "incidents.json"))
    monkeypatch.setenv("SECRET_KEY", "isolated-phase3-secret-key-32b")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'inventory.db').as_posix()}")
    get_settings.cache_clear()
    reset_db_for_tests()
    reset_engine_for_tests()
    yield
    reset_db_for_tests()
    reset_engine_for_tests()
    get_settings.cache_clear()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        "app.agent.graph.checkpoint_database_path",
        lambda: tmp_path / "checkpoints" / "support_agent.sqlite",
    )
    monkeypatch.setattr(
        "app.agent.graph.trace_directory",
        lambda: tmp_path / "traces",
    )
    application = FastAPI()
    application.include_router(router)
    return TestClient(application)


def _create_incident(*, status: str = "open") -> Any:
    return incident_service.create_incident(
        IncidentCreate(
            title=SEEDED_TITLE,
            description=SEEDED_DESCRIPTION,
            category="clinical_equipment",
            status=status,
            origin="branch",
            branch="central",
        )
    )


def _patch_mcp_from_incident_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for MCP with the local store. The graph node does not call it."""
    from app.agent.mcp_tickets import McpTicketError, TicketSnapshot
    from app.services.incident_service import IncidentNotFoundError

    def read_tickets(query: Any) -> list[TicketSnapshot]:
        if query.incident_id:
            try:
                row = incident_service.get_incident(query.incident_id)
            except IncidentNotFoundError as exc:
                raise McpTicketError("missing") from exc
            rows = [row]
        else:
            rows = incident_service.list_incidents(
                status=query.status,
                origin=query.origin,
                branch=query.branch,
                category=query.category,
            )
        return [
            TicketSnapshot(
                id=row.id,
                status=row.status,
                category=row.category,
                origin=row.origin,
                branch=row.branch,
            )
            for row in rows
        ]

    monkeypatch.setattr("app.agent.mcp_tickets.read_tickets_via_mcp", read_tickets)


def _assert_no_seeded_body(text: str) -> None:
    assert SEEDED_TITLE not in text
    assert SEEDED_DESCRIPTION not in text


def test_classifier_matches_the_routing_cases() -> None:
    assert classify_question("   ") == "empty"
    assert classify_question("How long does an internal referral take?") == "knowledge"
    assert classify_question("How is incident reporting supposed to work?") == "knowledge"
    assert classify_question("What is the capital of France?") == "knowledge"
    assert classify_question("What is the status of ticket 482?") == "ticket"
    assert classify_question("What is the status of incident HC-000482?") == "ticket"
    assert classify_question("Which incidents have status discarded?") == "ticket"
    sample = "11111111-1111-1111-1111-111111111111"
    assert classify_question(f"What is the status of incident {sample}?") == "ticket"
    assert (
        classify_question(
            f"What is the status of incident {sample}? How long does an internal referral take?"
        )
        == "both"
    )


def test_knowledge_only_and_empty_question_preserve_part_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_rag(monkeypatch)
    service_calls = {"n": 0}

    def fail_get(*_args: object, **_kwargs: object) -> None:
        service_calls["n"] += 1
        raise AssertionError("knowledge path called the incident service")

    monkeypatch.setattr("app.services.incident_service.get_incident", fail_get)
    monkeypatch.setattr("app.services.incident_service.list_incidents", fail_get)
    monkeypatch.setattr(
        "app.agent.mcp_tickets.read_tickets_via_mcp",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("knowledge path called MCP")
        ),
    )
    before = handoff_count()

    _outcome, stored = _run(
        tmp_path,
        "How long does an internal referral take?",
        authenticated=False,
    )
    assert stored["sources"] == ["rag"]
    assert stored["node_order"] == [
        "receive_question",
        "retrieve_context",
        "generate_from_context",
    ]
    assert "lookup_ticket" not in stored["node_order"]
    assert stored["answer"] == RAG_ANSWER
    assert calls["retrieve"] == 1
    assert service_calls["n"] == 0
    assert handoff_count() == before

    empty_outcome, empty_trace = _run(tmp_path, "   \n\t", authenticated=False)
    assert empty_trace["node_order"] == ["receive_question", "reject_question"]
    assert empty_trace["sources"] == []
    assert empty_outcome.error
    assert service_calls["n"] == 0


def test_ambiguous_policy_question_uses_rag_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_rag(monkeypatch)
    monkeypatch.setattr(
        "app.agent.mcp_tickets.read_tickets_via_mcp",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("lookup ran")),
    )
    _outcome, stored = _run(
        tmp_path,
        "How is incident reporting supposed to work?",
        authenticated=False,
    )
    assert stored["sources"] == ["rag"]
    assert "lookup_ticket" not in stored["node_order"]
    assert "retrieve_context" in stored["node_order"]
    for word in STATUS_WORDS:
        assert word not in stored["answer"]


def test_ticket_only_and_filters_read_the_real_service(
    isolated_stores: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_rag(monkeypatch)
    _patch_mcp_from_incident_store(monkeypatch)
    created = _create_incident(status="open")
    question = f"What is the status of incident {created.id}?"
    outcome, stored = _run(tmp_path, question, authenticated=True)
    fresh = incident_service.get_incident(created.id)

    assert stored["sources"] == ["ticket_tool"]
    assert "lookup_ticket" in stored["node_order"]
    assert "retrieve_context" not in stored["node_order"]
    assert "generate_from_context" not in stored["node_order"]
    assert fresh.status in outcome.answer
    assert fresh.id in outcome.answer
    assert fresh.category in outcome.answer
    assert fresh.origin in outcome.answer
    assert stored["ticket_id"] == fresh.id
    assert stored["ticket_status"] == fresh.status
    _assert_no_seeded_body(outcome.answer)
    _assert_no_seeded_body(str(stored))

    listed, listed_trace = _run(
        tmp_path,
        "Which incidents have status open?",
        authenticated=True,
    )
    assert listed_trace["sources"] == ["ticket_tool"]
    assert fresh.id in listed.answer
    assert "resolved" not in listed.answer
    assert "in_progress" not in listed.answer
    assert "discarded" not in listed.answer


def test_lookup_node_does_not_call_the_incident_service() -> None:
    lookup = __import__("app.agent.nodes", fromlist=["lookup_ticket"]).lookup_ticket
    node_source = Path(lookup.__code__.co_filename).read_text(encoding="utf-8")
    assert "incident_service" not in lookup.__code__.co_names
    assert "read_tickets_via_mcp" in lookup.__code__.co_names
    assert "incident_service.get_incident" not in node_source
    assert "incident_service.list_incidents" not in node_source
    assert "read_ticket_rows" not in node_source


def test_missing_unsupported_empty_filter_and_service_error(
    isolated_stores: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_rag(monkeypatch)
    _patch_mcp_from_incident_store(monkeypatch)
    missing_id = "22222222-2222-2222-2222-222222222222"
    _outcome, stored = _run(
        tmp_path,
        f"What is the status of incident {missing_id}?",
        authenticated=True,
    )
    assert stored["sources"] == ["ticket_tool"]
    assert stored["answer"] == HONEST_STATUS_SENTENCE
    assert stored["lookup_failure"] == "missing"
    for word in STATUS_WORDS:
        assert word not in stored["answer"]

    calls = {"get": 0, "list": 0}
    real_get = incident_service.get_incident
    real_list = incident_service.list_incidents

    def counting_get(incident_id: str) -> Any:
        calls["get"] += 1
        return real_get(incident_id)

    def counting_list(**kwargs: object) -> list[Any]:
        calls["list"] += 1
        return real_list(**kwargs)

    monkeypatch.setattr("app.services.incident_service.get_incident", counting_get)
    monkeypatch.setattr("app.services.incident_service.list_incidents", counting_list)
    for question in (
        "What is the status of ticket 482?",
        "What is the status of incident HC-000482?",
    ):
        _unsupported, unsupported_trace = _run(tmp_path, question, authenticated=True)
        assert unsupported_trace["answer"] == HONEST_STATUS_SENTENCE
        assert unsupported_trace["lookup_failure"] == "unsupported"
        assert unsupported_trace["sources"] == ["ticket_tool"]
    assert calls == {"get": 0, "list": 0}

    _empty, empty_trace = _run(
        tmp_path,
        "Which incidents have status discarded?",
        authenticated=True,
    )
    assert empty_trace["answer"] == HONEST_STATUS_SENTENCE
    assert empty_trace["sources"] == ["ticket_tool"]
    assert "discarded" not in empty_trace["answer"]

    def explode(_incident_id: str) -> None:
        raise RuntimeError("SERVICE_BLEW_UP")

    monkeypatch.setattr("app.services.incident_service.get_incident", explode)
    failed, failed_trace = _run(
        tmp_path,
        f"What is the status of incident {missing_id}?",
        authenticated=True,
    )
    assert failed.error == ""
    assert failed_trace["answer"] == HONEST_STATUS_SENTENCE
    assert failed_trace["lookup_failure"] == "error"
    assert "lookup_ticket" in failed_trace["node_order"]
    assert "SERVICE_BLEW_UP" not in str(failed_trace)
    for word in STATUS_WORDS:
        assert word not in failed.answer


def test_combined_success_and_combined_missing(
    isolated_stores: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_rag(monkeypatch)
    _patch_mcp_from_incident_store(monkeypatch)
    created = _create_incident(status="in_progress")
    question = (
        f"What is the status of incident {created.id}? "
        "How long does an internal referral take?"
    )
    outcome, stored = _run(tmp_path, question, authenticated=True)
    assert stored["sources"] == ["ticket_tool", "rag"]
    assert stored["node_order"].index("lookup_ticket") < stored["node_order"].index(
        "retrieve_context"
    )
    assert "in_progress" in outcome.answer
    assert RAG_ANSWER in outcome.answer
    _assert_no_seeded_body(str(stored))

    missing = (
        "What is the status of incident 33333333-3333-3333-3333-333333333333? "
        "How long does an internal referral take?"
    )
    combined, combined_trace = _run(tmp_path, missing, authenticated=True)
    assert combined_trace["sources"] == ["ticket_tool", "rag"]
    assert HONEST_STATUS_SENTENCE in combined.answer
    assert RAG_ANSWER in combined.answer
    for word in STATUS_WORDS:
        assert word not in combined.answer


def test_slot_is_single_and_times_out_without_a_pool() -> None:
    slot_source = Path(run_bounded_read.__code__.co_filename).read_text(encoding="utf-8")
    assert INCIDENT_LOOKUP_TIMEOUT_SECONDS == 5
    assert isinstance(INCIDENT_LOOKUP_TIMEOUT_SECONDS, int)
    assert "ThreadPoolExecutor(" not in slot_source

    ready = run_bounded_read(lambda: "ready")
    assert ready.failure is None and ready.rows == "ready"
    assert worker_is_daemon()

    release = threading.Event()
    entered = threading.Event()
    entries = {"n": 0}
    entry_lock = threading.Lock()

    def slow() -> str:
        with entry_lock:
            entries["n"] += 1
        entered.set()
        release.wait(timeout=30)
        return "finished"

    start_handoff = handoff_count()
    barrier = threading.Barrier(3)
    results: list[tuple[str | None, float]] = []
    result_lock = threading.Lock()

    def caller() -> None:
        barrier.wait()
        started = time.monotonic()
        outcome = run_bounded_read(slow)
        elapsed = time.monotonic() - started
        with result_lock:
            results.append((outcome.failure, elapsed))

    threads = [threading.Thread(target=caller) for _ in range(3)]
    try:
        for thread in threads:
            thread.start()
        assert entered.wait(timeout=2)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and sum(item[0] == "capacity" for item in results) < 2:
            time.sleep(0.01)
        assert entries["n"] == 1
        assert handoff_count() - start_handoff == 1
        assert in_flight_count() == 1
        for thread in threads:
            thread.join(timeout=8)
        capacity = [item for item in results if item[0] == "capacity"]
        winner = [item for item in results if item[0] == "timeout"]
        assert len(capacity) == 2
        assert all(elapsed < 1 for _failure, elapsed in capacity)
        assert len(winner) == 1
        assert winner[0][1] >= 4.5
        assert in_flight_count() == 1
        assert handoff_count() - start_handoff == 1
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=5)

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and in_flight_count() != 0:
        time.sleep(0.01)
    assert in_flight_count() == 0
    follow_up = run_bounded_read(lambda: "after")
    assert follow_up.failure is None and follow_up.rows == "after"


def test_graph_timeout_returns_before_the_read_finishes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    entered = threading.Event()

    def slow(_query: object) -> None:
        entered.set()
        release.wait(timeout=30)
        raise AssertionError("the timed-out read must not become the answer")

    monkeypatch.setattr("app.agent.mcp_tickets.read_tickets_via_mcp", slow)
    question = "What is the status of incident 44444444-4444-4444-4444-444444444444?"
    started = time.monotonic()
    try:
        outcome, stored = _run(tmp_path, question, authenticated=True)
        elapsed = time.monotonic() - started
        assert entered.is_set()
        assert outcome.error == ""
        assert stored["answer"] == HONEST_STATUS_SENTENCE
        assert stored["lookup_failure"] == "timeout"
        assert "lookup_ticket" in stored["node_order"]
        assert elapsed >= 4.5
        assert in_flight_count() == 1
    finally:
        release.set()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and in_flight_count() != 0:
        time.sleep(0.01)
    assert in_flight_count() == 0


def test_public_knowledge_and_unauthorized_ticket_routes(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_rag(monkeypatch)
    service_calls = {"n": 0}
    auth_calls = {"n": 0}

    def fail_service(*_args: object, **_kwargs: object) -> None:
        service_calls["n"] += 1
        raise AssertionError("public route called the incident service")

    def count_auth(token: str) -> Any:
        auth_calls["n"] += 1
        raise AssertionError(token)

    monkeypatch.setattr("app.services.incident_service.get_incident", fail_service)
    monkeypatch.setattr("app.services.incident_service.list_incidents", fail_service)
    monkeypatch.setattr("app.routers.agent.get_current_user", count_auth)

    knowledge = client.post(
        "/agent/query",
        json={"question": "How long does an internal referral take?"},
    )
    assert knowledge.status_code == 200
    assert knowledge.json()["answer"] == RAG_ANSWER
    assert service_calls["n"] == 0
    assert auth_calls["n"] == 0

    def fail_graph(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("ticket route ran the graph without a bearer")

    monkeypatch.setattr("app.routers.agent.run_support_agent", fail_graph)
    for question in (
        "What is the status of ticket 482?",
        "What is the status of ticket 482? How long does an internal referral take?",
    ):
        response = client.post("/agent/query", json={"question": question})
        assert response.status_code == 401
        assert response.json()["detail"] == "Could not validate credentials"
        assert SEEDED_TITLE not in response.text
    assert service_calls["n"] == 0


def test_authenticated_routes_follow_the_question(
    isolated_stores: None,
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_rag(monkeypatch)
    _patch_mcp_from_incident_store(monkeypatch)
    created = _create_incident(status="open")
    user = user_service.create_user(
        UserCreate(email="agent-phase3@example.com", password="TestPass123")
    )
    token = create_access_token(subject=user.id)
    order: list[str] = []
    real_auth = __import__("app.routers.agent", fromlist=["get_current_user"]).get_current_user
    real_get = incident_service.get_incident

    def wrapped_auth(raw_token: str) -> Any:
        order.append("auth")
        return real_auth(raw_token)

    def wrapped_get(incident_id: str) -> Any:
        order.append("read")
        return real_get(incident_id)

    monkeypatch.setattr("app.routers.agent.get_current_user", wrapped_auth)
    monkeypatch.setattr("app.services.incident_service.get_incident", wrapped_get)
    headers = {"Authorization": f"Bearer {token}"}

    ticket = client.post(
        "/agent/query",
        headers=headers,
        json={"question": f"What is the status of incident {created.id}?"},
    )
    assert ticket.status_code == 200
    assert order[0] == "auth"
    assert "read" in order
    assert created.id in ticket.json()["answer"]
    assert "open" in ticket.json()["answer"]
    stored = load_trace(ticket.json()["trace_id"], tmp_path / "traces")
    assert stored["sources"] == ["ticket_tool"]
    assert "retrieve_context" not in stored["node_order"]
    _assert_no_seeded_body(str(stored))

    order.clear()
    combined = client.post(
        "/agent/query",
        headers=headers,
        json={
            "question": (
                f"What is the status of incident {created.id}? "
                "How long does an internal referral take?"
            )
        },
    )
    assert combined.status_code == 200
    assert order[0] == "auth"
    body = combined.json()["answer"]
    assert "open" in body
    assert RAG_ANSWER in body
    combined_trace = load_trace(combined.json()["trace_id"], tmp_path / "traces")
    assert combined_trace["sources"] == ["ticket_tool", "rag"]


def test_route_and_graph_disagreement_does_not_read_the_service(
    isolated_stores: None,
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = _create_incident(status="resolved")
    calls = {"n": 0}

    def fail_get(*_args: object, **_kwargs: object) -> None:
        calls["n"] += 1
        raise AssertionError("disagreement path called get_incident")

    monkeypatch.setattr("app.services.incident_service.get_incident", fail_get)
    monkeypatch.setattr("app.services.incident_service.list_incidents", fail_get)
    monkeypatch.setattr("app.agent.mcp_tickets.read_tickets_via_mcp", fail_get)
    monkeypatch.setattr("app.routers.agent.classify_question", lambda _question: "knowledge")

    question = f"What is the status of incident {created.id}?"
    response = client.post("/agent/query", json={"question": question})
    assert response.status_code == 200
    assert calls["n"] == 0
    assert response.json()["answer"] == HONEST_STATUS_SENTENCE
    stored = load_trace(response.json()["trace_id"], tmp_path / "traces")
    assert stored["question"] == question
    assert created.id in stored["question"]
    assert "lookup_ticket" in stored["node_order"]
    assert stored["lookup_failure"] == "unauthorized"
    assert stored["ticket_id"] == ""
    assert stored["ticket_status"] == ""
    trace_text = str(stored)
    _assert_no_seeded_body(trace_text)
    _assert_no_seeded_body(response.text)
    assert "resolved" not in response.text
    assert "resolved" not in trace_text
