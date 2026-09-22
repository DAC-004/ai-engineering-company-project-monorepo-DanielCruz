"""Endpoint tests for POST /agent/query on a minimal FastAPI app.

The full HealthCore app is not started, so inventory database setup and
secret loading from the application lifespan do not run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.agent.nodes import EMPTY_QUESTION_ERROR  # noqa: E402
from app.agent.tracing import load_trace  # noqa: E402
from app.routers.agent import AGENT_FAILURE_DETAIL, router  # noqa: E402


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


def test_agent_query_returns_answer_and_trace_id(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "source_document": "referral-process",
        "text": "Target completed-referral time: 11 days from creation to confirmed appointment.",
    }
    monkeypatch.setattr("data.pipelines.rag.retrieve", lambda _query, **_kwargs: [payload])
    monkeypatch.setattr(
        "data.pipelines.rag.generate_answer",
        lambda _question, context: "The indexed policy says 11 days.",
    )

    response = client.post(
        "/agent/query",
        json={"question": "How long does an internal referral take?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "The indexed policy says 11 days."
    assert body["trace_id"]
    assert "Traceback" not in response.text
    stored = load_trace(body["trace_id"], tmp_path / "traces")
    assert stored["context"] == [payload]
    assert "11 days" in stored["answer"]


def test_empty_question_returns_http_400(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_retrieve(*_args: object, **_kwargs: object) -> list[dict[str, str]]:
        raise AssertionError("retrieve() should not run for an empty question")

    monkeypatch.setattr("data.pipelines.rag.retrieve", fail_retrieve)
    response = client.post("/agent/query", json={"question": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == EMPTY_QUESTION_ERROR
    assert "Traceback" not in response.text
    assert "sqlite" not in response.text.lower()


def test_unexpected_failure_returns_http_502_without_internal_detail(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(_question: str, **_kwargs: object) -> None:
        raise RuntimeError("INTERNAL_STACK_DETAIL")

    monkeypatch.setattr("app.routers.agent.run_support_agent", explode)
    response = client.post("/agent/query", json={"question": "How long is a referral?"})

    assert response.status_code == 502
    assert response.json()["detail"] == AGENT_FAILURE_DETAIL
    assert "INTERNAL_STACK_DETAIL" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text
