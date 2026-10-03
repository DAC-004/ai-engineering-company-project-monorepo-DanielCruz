"""Executing Part 2 routing evals.

Run the default command from ``services/api`` with ``PART2_LIVE_RAG_EVAL``
unset. A fresh clone does not contain the ignored Qdrant index or GGUF.

    uv run pytest --rootdir . ../../tests/pipelines/test_agent_phase4_evals.py -q -p no:cacheprovider --tb=short

That command executes three tests and skips the live retrieval test before
any RAG call:

- ``test_ticket_eval_reads_the_real_service_twice`` creates and updates a
  ticket through the Incident Manager HTTP API, then the graph reads it
  twice through MCP. It does not patch the lookup.
- ``test_knowledge_routing_eval_patches_retrieval_and_generation`` runs the
  compiled graph. Only ``retrieve()`` and ``generate_answer()`` are patched,
  using text from the committed referral-policy document.
- ``test_failure_eval_finishes_without_a_fabricated_status`` asks MCP for a
  UUID the API does not have. A missing ticket is ``lookup_failure``
  ``missing``. A connection or authentication failure stays ``error``.

Opt-in live retrieval, in PowerShell, still from ``services/api``:

    $env:PART2_LIVE_RAG_EVAL = "1"
    uv run pytest --rootdir . ../../tests/pipelines/test_agent_phase4_evals.py -q -p no:cacheprovider --tb=short -k test_knowledge_eval_uses_real_retrieval_and_local_generation

``test_knowledge_eval_uses_real_retrieval_and_local_generation`` then checks
that the local index and GGUF exist, and only after that calls real
``retrieve()`` and local generation. It does not download a model.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_SHARED = REPO_ROOT / "packages" / "shared"
API_ROOT = REPO_ROOT / "services" / "api"
for _import_path in (API_ROOT, REPO_ROOT, PACKAGES_SHARED):
    if str(_import_path) not in sys.path:
        sys.path.insert(0, str(_import_path))

from app.agent.graph import run_support_agent
from app.agent.routing import HONEST_STATUS_SENTENCE
from app.agent.tracing import load_trace

REFERRAL_DOCUMENT = (
    REPO_ROOT / "docs" / "company-knowledge-base" / "healthcore-referral-process.en.md"
)
TRACE_DIR = REPO_ROOT / "data" / "process" / "agent_traces"
CHECKPOINT_PATH = REPO_ROOT / "data" / "process" / "agent_checkpoints" / "phase4_evals.sqlite"
LIVE_RAG_EVAL_ENV = "PART2_LIVE_RAG_EVAL"
POLICY_SENTENCE = (
    "Target completed-referral time: 11 days from creation to confirmed appointment"
)
STATUS_WORDS = ("open", "in_progress", "resolved", "discarded")
_ANSWER_FIELDS = re.compile(
    r"Incident (?P<id>[0-9a-fA-F-]{36}) status is (?P<status>[A-Za-z0-9_]+)\. "
    r"Category: (?P<category>[A-Za-z0-9_]+)\. Origin: (?P<origin>[A-Za-z0-9_]+)\."
)


def _policy_sentence() -> str:
    """Load the referral timing sentence from the policy file.

    The file wraps the sentence and continues with a parenthetical. The
    approved fact is the wording through ``appointment``, read from the file
    rather than from a graph trace.
    """
    collapsed = " ".join(REFERRAL_DOCUMENT.read_text(encoding="utf-8").split())
    if POLICY_SENTENCE not in collapsed:
        raise AssertionError("The referral policy file does not contain the 11-day sentence.")
    if "11 days" not in POLICY_SENTENCE:
        raise AssertionError("The policy sentence does not contain the 11-day fact.")
    return POLICY_SENTENCE


def _live_rag_requested() -> bool:
    return os.environ.get(LIVE_RAG_EVAL_ENV, "").strip().lower() in {"1", "true", "yes"}


def _require_local_rag_assets() -> None:
    """Fail before the graph runs when the ignored local assets are absent.

    ``generate_answer()`` downloads the GGUF when that file is missing.
    This check runs first so the opt-in eval never reaches that download
    and never replaces the live path with a mock.
    """
    from shared.healthcore_rag.config import (
        COLLECTION_NAME,
        GENERATION_API_KEY,
        LOCAL_GENERATION_GGUF_FILENAME,
        MODELS_DIR,
        QDRANT_PATH,
        QDRANT_URL,
    )

    if QDRANT_URL:
        pytest.fail(
            "Unset QDRANT_URL before the live RAG eval so retrieval uses the "
            "local embedded index."
        )
    if GENERATION_API_KEY:
        pytest.fail(
            "Unset GENERATION_API_KEY before the live RAG eval so generation "
            "uses the local GGUF instead of a remote model."
        )

    index_file = Path(QDRANT_PATH) / "collection" / COLLECTION_NAME / "storage.sqlite"
    model_file = MODELS_DIR / LOCAL_GENERATION_GGUF_FILENAME
    missing: list[str] = []
    if not index_file.is_file():
        missing.append(f"Qdrant collection file {index_file}")
    if not model_file.is_file() or model_file.stat().st_size <= 0:
        missing.append(f"GGUF file {model_file}")
    if missing:
        pytest.fail(
            f"{LIVE_RAG_EVAL_ENV} is set, but the local RAG assets are absent: "
            + "; ".join(missing)
            + ". Place those ignored files locally. This test does not download "
            "a model and does not substitute mocked retrieval."
        )


def _run(question: str, *, authenticated: bool) -> tuple[object, dict]:
    outcome = run_support_agent(
        question,
        caller_is_authenticated=authenticated,
        checkpoint_path=CHECKPOINT_PATH,
        trace_dir=TRACE_DIR,
    )
    return outcome, load_trace(outcome.trace_id, TRACE_DIR)


def _answer_fields(answer: str) -> dict[str, str]:
    match = _ANSWER_FIELDS.search(answer)
    if match is None:
        raise AssertionError(f"Answer did not report id, status, category, and origin: {answer}")
    return match.groupdict()


def _assert_matches_read(answer: str, row: object) -> None:
    reported = _answer_fields(answer)
    assert reported["id"] == row.id
    assert reported["status"] == row.status
    assert reported["category"] == row.category
    assert reported["origin"] == row.origin


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class IncidentManagerStack:
    """API plus MCP for evals that must not read TinyDB inside the graph.

    The graph process receives only an MCP bearer token. Ticket writes go to
    the Incident Manager HTTP API. MCP then reads that same API.
    """

    def __init__(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="phase4-mcp-"))
        self.api_port = _free_port()
        self.mcp_port = _free_port()
        self.api_base_url = f"http://127.0.0.1:{self.api_port}"
        self.resource_url = f"http://127.0.0.1:{self.mcp_port}/mcp"
        self.username = "phase4-mcp-reader@healthcore.com"
        self.password = "Phase4McpEval1!"
        self.agent_token = ""
        self.http: httpx.Client | None = None
        self.oidc = None
        self.api_process: subprocess.Popen[str] | None = None
        self.mcp_process: subprocess.Popen[str] | None = None
        self.api_log = self.temp_dir / "api.log"
        self.mcp_log = self.temp_dir / "mcp.log"
        self._log_files: list[object] = []

    def start(self) -> None:
        mcp_tests = REPO_ROOT / "mcps" / "healthcore-tools" / "tests"
        if str(mcp_tests) not in sys.path:
            sys.path.insert(0, str(mcp_tests))
        from oidc_fixture import start_oidc_issuer

        self.oidc = start_oidc_issuer(_free_port())
        self.agent_token = self.oidc.mint_access_token(
            audience=self.resource_url,
            scopes=["healthcore:mcp", "incidents:read"],
            client_id="phase4-agent",
        )
        self._start_api()
        self.http = httpx.Client(base_url=self.api_base_url, timeout=30.0)
        created = self.http.post(
            "/users",
            json={"email": self.username, "password": self.password},
        )
        if created.status_code not in (200, 201):
            raise RuntimeError(f"Could not register API user: {created.status_code} {created.text}")
        self._start_mcp()

    def stop(self) -> None:
        if self.mcp_process is not None and self.mcp_process.poll() is None:
            self.mcp_process.terminate()
            self.mcp_process.wait(timeout=5)
        if self.http is not None:
            self.http.close()
        if self.oidc is not None:
            self.oidc.stop()
        if self.api_process is not None and self.api_process.poll() is None:
            self.api_process.terminate()
            self.api_process.wait(timeout=5)
        for log_file in self._log_files:
            close = getattr(log_file, "close", None)
            if close is not None:
                close()

    def authorize_graph(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Point the graph at this MCP server. The token is not written to disk."""
        monkeypatch.setenv("MCP_RESOURCE_URL", self.resource_url)
        monkeypatch.setenv("MCP_AGENT_ACCESS_TOKEN", self.agent_token)

    def create_incident(self) -> SimpleNamespace:
        response = self._authed(
            "POST",
            "/api/incidents",
            json={
                "title": "Synthetic pump alarm",
                "description": "Phase 4 synthetic ticket body",
                "category": "clinical_equipment",
                "status": "open",
                "origin": "branch",
                "branch": "central",
            },
        )
        return _incident_row(response.json())

    def update_status(self, incident_id: str, status: str) -> SimpleNamespace:
        response = self._authed(
            "PATCH",
            f"/api/incidents/{incident_id}/status",
            json={"status": status},
        )
        return _incident_row(response.json())

    def get_incident(self, incident_id: str) -> SimpleNamespace:
        response = self._authed("GET", f"/api/incidents/{incident_id}")
        return _incident_row(response.json())

    def _authed(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        if self.http is None:
            raise RuntimeError("The Incident Manager stack is not started.")
        login = self.http.post(
            "/auth/login",
            data={"username": self.username, "password": self.password},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        response = self.http.request(
            method,
            path,
            headers={"Authorization": f"Bearer {token}"},
            **kwargs,
        )
        response.raise_for_status()
        return response

    def _start_api(self) -> None:
        env = os.environ.copy()
        env["SECRET_KEY"] = "phase4-mcp-secret-key-32b"
        env["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
        env["JWT_ALGORITHM"] = "HS256"
        env["TINYDB_PATH"] = str(self.temp_dir / "incidents.json")
        env["DATABASE_URL"] = f"sqlite:///{(self.temp_dir / 'inventory.db').as_posix()}"
        self.api_process = self._popen(
            [
                "uv",
                "run",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.api_port),
                "--log-level",
                "warning",
            ],
            cwd=API_ROOT,
            env=env,
            log_path=self.api_log,
        )
        self._wait_http(f"{self.api_base_url}/health", self.api_process, self.api_log, "API")

    def _start_mcp(self) -> None:
        if self.oidc is None:
            raise RuntimeError("OIDC issuer is not started.")
        env = os.environ.copy()
        env["MCP_AUTH_ISSUER"] = self.oidc.issuer
        env["MCP_RESOURCE_URL"] = self.resource_url
        env["MCP_HOST"] = "127.0.0.1"
        env["MCP_PORT"] = str(self.mcp_port)
        env["HEALTHCORE_API_BASE_URL"] = self.api_base_url
        env["HEALTHCORE_API_USERNAME"] = self.username
        env["HEALTHCORE_API_PASSWORD"] = self.password
        self.mcp_process = self._popen(
            ["uv", "run", "healthcore-tools"],
            cwd=REPO_ROOT / "mcps" / "healthcore-tools",
            env=env,
            log_path=self.mcp_log,
        )
        metadata = (
            f"http://127.0.0.1:{self.mcp_port}/.well-known/oauth-protected-resource/mcp"
        )
        self._wait_http(metadata, self.mcp_process, self.mcp_log, "MCP")

    def _popen(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        log_path: Path,
    ) -> subprocess.Popen[str]:
        log_file = log_path.open("w", encoding="utf-8")
        self._log_files.append(log_file)
        return subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def _wait_http(
        self,
        url: str,
        process: subprocess.Popen[str] | None,
        log_path: Path,
        label: str,
    ) -> None:
        deadline = time.time() + 40
        last_error = "no response"
        while time.time() < deadline:
            if process is not None and process.poll() is not None:
                break
            try:
                response = httpx.get(url, timeout=1.0)
            except httpx.HTTPError as exc:
                last_error = str(exc)
                time.sleep(0.2)
                continue
            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}"
            time.sleep(0.2)
        log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
        raise RuntimeError(f"{label} did not start ({last_error}). Log:\n{log_text[-2000:]}")


def _incident_row(payload: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=payload["id"],
        status=payload["status"],
        category=payload["category"],
        origin=payload["origin"],
        title=payload["title"],
        description=payload["description"],
    )


@pytest.fixture(scope="module")
def incident_mcp() -> object:
    stack = IncidentManagerStack()
    try:
        stack.start()
        yield stack
    finally:
        stack.stop()


def test_ticket_eval_reads_the_real_service_twice(
    incident_mcp: IncidentManagerStack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incident_mcp.authorize_graph(monkeypatch)
    created = incident_mcp.create_incident()
    question = f"What is the status of incident {created.id}?"
    assert "knowledge base" not in question.lower()
    assert "use the tool" not in question.lower()

    first_outcome, first_trace = _run(question, authenticated=True)
    first_read = incident_mcp.get_incident(created.id)
    assert first_trace["sources"] == ["ticket_tool"]
    assert "lookup_ticket" in first_trace["node_order"]
    assert "retrieve_context" not in first_trace["node_order"]
    assert first_trace["lookup_failure"] == ""
    _assert_matches_read(str(first_outcome.answer), first_read)
    _assert_no_ticket_body(first_trace, created.title, created.description)

    incident_mcp.update_status(created.id, "in_progress")
    second_outcome, second_trace = _run(question, authenticated=True)
    second_read = incident_mcp.get_incident(created.id)
    assert second_read.status == "in_progress"
    assert second_trace["sources"] == ["ticket_tool"]
    assert second_trace["lookup_failure"] == ""
    assert "retrieve_context" not in second_trace["node_order"]
    _assert_matches_read(str(second_outcome.answer), second_read)
    assert second_read.status in str(second_outcome.answer)
    assert first_read.status not in _answer_fields(str(second_outcome.answer))["status"]
    _assert_no_ticket_body(second_trace, created.title, created.description)


def test_knowledge_routing_eval_patches_retrieval_and_generation(monkeypatch) -> None:
    """Asset-free knowledge routing. Retrieval and generation are patched.

    The compiled graph still chooses the nodes and writes the trace.
    ``retrieve()`` returns a chunk copied from the referral-policy file.
    ``generate_answer()`` copies that chunk into the answer, so a bypassed
    generator or a missing context fails the assertion.
    """
    sentence = _policy_sentence()
    calls = {"retrieve": 0, "generate": 0}
    service_calls = {"n": 0}

    def fail_incident_read(*_args: object, **_kwargs: object) -> None:
        service_calls["n"] += 1
        raise AssertionError("patched knowledge eval called an incident read")

    def patched_retrieve(_query: str, **_kwargs: object) -> list[dict[str, object]]:
        calls["retrieve"] += 1
        return [
            {
                "company": "healthcore",
                "source_document": "referral-process",
                "section": "Target completed-referral time",
                "language": "en",
                "chunk_index": 1,
                "text": sentence,
            }
        ]

    def patched_generate(_question: str, context: list[object]) -> str:
        """Return the supplied chunk text, or a marker when it is missing."""
        calls["generate"] += 1
        retrieved_text = " ".join(
            str(chunk.get("text", ""))
            for chunk in context
            if isinstance(chunk, dict)
        )
        if sentence not in retrieved_text:
            return "UNGROUNDED"
        return f"The retrieved referral policy says: {retrieved_text}"

    monkeypatch.setattr("data.pipelines.rag.retrieve", patched_retrieve)
    monkeypatch.setattr("data.pipelines.rag.generate_answer", patched_generate)
    monkeypatch.setattr("app.services.incident_service.get_incident", fail_incident_read)
    monkeypatch.setattr("app.services.incident_service.list_incidents", fail_incident_read)

    question = "How long does an internal referral take?"
    outcome, stored = _run(question, authenticated=False)
    assert calls["retrieve"] == 1
    assert calls["generate"] == 1
    assert service_calls["n"] == 0
    assert stored["sources"] == ["rag"]
    assert "lookup_ticket" not in stored["node_order"]
    assert stored["node_order"].index("retrieve_context") < stored["node_order"].index(
        "generate_from_context"
    )
    retrieved_chunks = [
        chunk
        for chunk in stored["context"]
        if isinstance(chunk, dict) and chunk.get("source_document") == "referral-process"
    ]
    assert retrieved_chunks
    assert sentence in str(retrieved_chunks[0].get("text", ""))
    assert sentence in str(outcome.answer)
    assert "11 days" in str(outcome.answer)
    generated = next(
        node for node in stored["nodes"] if node["node"] == "generate_from_context"
    )
    assert sentence in str(generated["output"].get("answer", ""))
    for word in STATUS_WORDS:
        assert word not in str(outcome.answer)
    assert stored["error"] == ""


def test_knowledge_eval_uses_real_retrieval_and_local_generation() -> None:
    """Live retrieval and local GGUF generation. Opt in with PART2_LIVE_RAG_EVAL.

    Without the variable this returns before any RAG call. With the variable
    set, missing local assets fail here instead of downloading a model.
    """
    if not _live_rag_requested():
        pytest.skip(
            f"Set {LIVE_RAG_EVAL_ENV}=1 to run real Qdrant retrieval and local "
            "GGUF generation. The default Part 2 eval skips this test and does "
            "not download a model."
        )
    _require_local_rag_assets()
    sentence = _policy_sentence()
    phrase = "11 days"
    assert phrase in sentence

    question = "How long does an internal referral take?"
    outcome, stored = _run(question, authenticated=False)
    assert stored["sources"] == ["rag"]
    assert "retrieve_context" in stored["node_order"]
    assert "generate_from_context" in stored["node_order"]
    assert "lookup_ticket" not in stored["node_order"]
    assert stored["node_order"].index("retrieve_context") < stored["node_order"].index(
        "generate_from_context"
    )
    referral_chunks = [
        chunk
        for chunk in stored["context"]
        if isinstance(chunk, dict) and chunk.get("source_document") == "referral-process"
    ]
    assert referral_chunks
    retrieved = " ".join(str(chunk.get("text", "")) for chunk in referral_chunks)
    assert phrase in retrieved
    assert phrase in str(outcome.answer)
    for word in STATUS_WORDS:
        assert word not in str(outcome.answer)
    assert stored["error"] == ""


def test_failure_eval_finishes_without_a_fabricated_status(
    incident_mcp: IncidentManagerStack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A UUID the API does not have is missing, not an MCP transport failure.

    ``lookup_failure`` is ``missing`` only after MCP accepts the agent token
    and the Incident Manager returns not found. Connection and authentication
    failures remain ``error``.
    """
    incident_mcp.authorize_graph(monkeypatch)
    question = "What is the status of incident 55555555-5555-4555-8555-555555555555?"
    outcome, stored = _run(question, authenticated=True)
    assert outcome.error == ""
    assert stored["answer"] == HONEST_STATUS_SENTENCE
    assert stored["lookup_failure"] == "missing"
    assert stored["lookup_failure"] != "error"
    assert "lookup_ticket" in stored["node_order"]
    assert (TRACE_DIR / f"{outcome.trace_id}.json").is_file()
    for word in STATUS_WORDS:
        assert word not in stored["answer"]


def _assert_no_ticket_body(stored: dict, title: str, description: str) -> None:
    trace_text = str(stored)
    assert title not in trace_text
    assert description not in trace_text
    assert stored["ticket_id"]
    assert stored["ticket_status"] in STATUS_WORDS
    assert stored["sources"] == ["ticket_tool"]
    assert "title" not in stored
    assert "description" not in stored
