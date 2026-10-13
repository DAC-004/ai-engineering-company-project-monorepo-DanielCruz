"""SSE framing, auth, accept trigger, and in-process replay.

These tests read the HTTP stream. They do not open the dashboard.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "services" / "api"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

# Share a sqlite database already chosen by another RFP test module.
# Replacing DATABASE_URL here used to point the process at a second file
# while the PHI tests still read the first path.
_owns_database = not os.environ.get("DATABASE_URL", "").startswith("sqlite")
if _owns_database:
    _tmpdir = tempfile.mkdtemp(prefix="rfp-sse-")
    _sqlite_path = (Path(_tmpdir) / "rfp.db").resolve().as_posix()
    os.environ["DATABASE_URL"] = f"sqlite:///{_sqlite_path}"
    os.environ["TINYDB_PATH"] = str(Path(_tmpdir) / "auth.json")
os.environ.setdefault("SECRET_KEY", "rfp-sse-test-secret-key-32-chars")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("NLTK_DATA", str(REPO_ROOT / "data" / "process" / "nltk_data"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import (  # noqa: E402
    _backfill_classified_rfp_ids,
    get_engine,
    reset_engine_for_tests,
)
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from app.rfp_models import RfpMetadata, RfpTicket  # noqa: E402
from app.services import rfp_notifications, rfp_service  # noqa: E402
from data.pipelines.rfp_intake.graph import (  # noqa: E402
    _classify,
    bind_accept_callback,
    reset_accept_callback,
)
from data.pipelines.rfp_intake.runner import IntakeRun  # noqa: E402

get_settings.cache_clear()
if _owns_database:
    reset_db_for_tests()
    reset_engine_for_tests()


def _auth_header(client: TestClient) -> dict[str, str]:
    email = f"sse-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/users", json={"email": email, "password": "validpass1", "name": "SSE Tester"})
    login = client.post("/auth/login", data={"username": email, "password": "validpass1"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _payloads(body: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for block in body.split("\n\n"):
        data_line = next((line for line in block.split("\n") if line.startswith("data:")), None)
        if data_line is None:
            continue
        found.append(json.loads(data_line.removeprefix("data:").strip()))
    return found


@pytest.fixture(autouse=True)
def _clear_notifications():
    rfp_notifications.reset_for_tests()
    rfp_notifications.keepalive_seconds = 0.05
    yield
    rfp_notifications.reset_for_tests()


def test_missing_token_is_unauthorized() -> None:
    with TestClient(app) as client:
        response = client.get("/rfp/tickets/stream")
    assert response.status_code == 401
    assert "rfp_ticket_created" not in response.text
    assert "text/event-stream" not in response.headers.get("content-type", "")


def test_stream_replays_the_buffer_without_last_event_id() -> None:
    created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    first = rfp_notifications.publish_ticket_created(
        ticket_id="ticket-sse-1",
        rfp_id=str(uuid.uuid4()),
        status="analyzing",
        created_at=created_at,
    )
    second_rfp = str(uuid.uuid4())
    rfp_notifications.publish_ticket_created(
        ticket_id="ticket-sse-2",
        rfp_id=second_rfp,
        status="analyzing",
        created_at=created_at,
    )
    rfp_notifications.stop_after_chunks = 2
    with TestClient(app) as client:
        headers = _auth_header(client)
        response = client.get("/rfp/tickets/stream", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    body = response.text
    assert "event: rfp_ticket_created" in body
    assert ": replay-gap" not in body
    payloads = _payloads(body)
    assert [item["ticket_id"] for item in payloads] == ["ticket-sse-1", "ticket-sse-2"]
    assert payloads[1]["rfp_id"] == second_rfp
    assert payloads[1]["status"] == "analyzing"
    assert payloads[1]["created_at"] == created_at
    assert first.startswith(rfp_notifications._boot_id)


def test_known_last_event_id_replays_only_later_frames() -> None:
    created_at = "2026-10-01T17:00:00Z"
    first = rfp_notifications.publish_ticket_created(
        ticket_id="ticket-sse-early",
        rfp_id=str(uuid.uuid4()),
        status="analyzing",
        created_at=created_at,
    )
    rfp_notifications.publish_ticket_created(
        ticket_id="ticket-sse-later",
        rfp_id=str(uuid.uuid4()),
        status="analyzing",
        created_at=created_at,
    )
    rfp_notifications.stop_after_chunks = 1
    with TestClient(app) as client:
        headers = _auth_header(client)
        headers["Last-Event-ID"] = first
        response = client.get("/rfp/tickets/stream", headers=headers)
    body = response.text
    payloads = _payloads(body)
    assert [item["ticket_id"] for item in payloads] == ["ticket-sse-later"]
    assert ": replay-gap" not in body


def test_foreign_boot_id_emits_replay_gap_then_live_frames() -> None:
    rfp_notifications.stop_after_chunks = 2
    rfp_notifications.keepalive_seconds = 5

    def publish_live() -> None:
        rfp_notifications.publish_ticket_created(
            ticket_id="ticket-sse-live",
            rfp_id=str(uuid.uuid4()),
            status="analyzing",
            created_at="2026-10-01T17:05:00Z",
        )

    def publish_on_subscribe() -> None:
        threading.Thread(target=publish_live).start()

    rfp_notifications.during_subscribe = publish_on_subscribe
    with TestClient(app) as client:
        headers = _auth_header(client)
        headers["Last-Event-ID"] = "previous-boot:99"
        response = client.get("/rfp/tickets/stream", headers=headers)
    body = response.text
    assert body.index(": replay-gap") < body.index("event: rfp_ticket_created")
    assert _payloads(body)[0]["ticket_id"] == "ticket-sse-live"
    # The new sequence is 1. It must still arrive after cursor 99 from another boot.
    assert ": replay-gap" in body


def test_publish_during_subscribe_is_delivered_once() -> None:
    created_at = "2026-10-01T17:06:00Z"
    finished = threading.Event()

    def publish_while_locked() -> None:
        rfp_notifications.publish_ticket_created(
            ticket_id="ticket-sse-handoff",
            rfp_id=str(uuid.uuid4()),
            status="analyzing",
            created_at=created_at,
        )
        finished.set()

    def hold_lock_until_publish_waits() -> None:
        worker = threading.Thread(target=publish_while_locked)
        worker.start()
        assert not finished.wait(timeout=0.3)

    rfp_notifications.during_subscribe = hold_lock_until_publish_waits
    frames, gap, subscriber = rfp_notifications.subscribe(None)
    assert gap is False
    assert frames == []
    assert finished.wait(timeout=1)
    live = subscriber.get(timeout=1)
    assert "ticket-sse-handoff" in live
    assert subscriber.empty()


def test_replay_and_live_frames_name_one_ticket() -> None:
    created_at = "2026-10-01T17:07:00Z"
    rfp_id = str(uuid.uuid4())
    rfp_notifications.publish_ticket_created(
        ticket_id="ticket-sse-once",
        rfp_id=rfp_id,
        status="analyzing",
        created_at=created_at,
    )
    frames, gap, subscriber = rfp_notifications.subscribe(None)
    rfp_notifications.publish_ticket_created(
        ticket_id="ticket-sse-once",
        rfp_id=rfp_id,
        status="analyzing",
        created_at=created_at,
    )
    live = subscriber.get(timeout=1)
    ticket_ids = {json.loads(frame.split("data: ", 1)[1].split("\n", 1)[0])["ticket_id"] for frame in (*frames, live)}
    assert gap is False
    assert ticket_ids == {"ticket-sse-once"}


def test_accept_invokes_the_hook_and_discard_does_not(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def classify(markdown: str, complete_fn) -> dict[str, str]:
        del markdown, complete_fn
        return {"decision": "accept", "reason_code": "healthcore_rfp"}

    monkeypatch.setattr("data.pipelines.rfp_intake.graph.classify_rfp", classify)
    token = bind_accept_callback(lambda: calls.append("accept"))
    try:
        _classify({"screened_markdown": "institutional request", "classification": {}, "metadata": {}, "extracts": {}, "unknown_departments": [], "worker_results": [], "summary": "", "unresolved_disagreements": [], "output_phi": False, "node_trace": []})
    finally:
        reset_accept_callback(token)
    assert calls == ["accept"]

    calls.clear()

    def discard(markdown: str, complete_fn) -> dict[str, str]:
        del markdown, complete_fn
        return {"decision": "discard", "reason_code": "not_healthcore_rfp"}

    monkeypatch.setattr("data.pipelines.rfp_intake.graph.classify_rfp", discard)
    token = bind_accept_callback(lambda: calls.append("accept"))
    try:
        _classify({"screened_markdown": "unrelated document", "classification": {}, "metadata": {}, "extracts": {}, "unknown_departments": [], "worker_results": [], "summary": "", "unresolved_disagreements": [], "output_phi": False, "node_trace": []})
    finally:
        reset_accept_callback(token)
    assert calls == []


def test_accept_assigns_rfp_id_and_upload_or_later_status_does_not() -> None:
    with TestClient(app):
        with Session(get_engine()) as session:
            created = rfp_service.create_ticket(session)
            assert created.rfp_id is None
            assert len(rfp_notifications._buffer) == 0

            rfp_service.notify_classified_accept(session, created.ticket_id)
            session.refresh(created)
            first_rfp_id = created.rfp_id
            assert first_rfp_id is not None
            uuid.UUID(first_rfp_id)
            assert first_rfp_id != created.ticket_id
            assert not first_rfp_id.startswith("rfp-")
            assert created.status == "analyzing"
            assert len(rfp_notifications._buffer) == 1

            rfp_service.notify_classified_accept(session, created.ticket_id)
            session.refresh(created)
            assert created.rfp_id == first_rfp_id

            created.status = "discarded"
            created.rfp_id = None
            session.add(created)
            session.commit()
            before = len(rfp_notifications._buffer)
            rfp_service.notify_classified_accept(session, created.ticket_id)
            session.refresh(created)
            assert created.rfp_id is None
            assert len(rfp_notifications._buffer) == before

            created.status = "intake_complete"
            session.add(created)
            session.commit()
            rfp_service.notify_classified_accept(session, created.ticket_id)
            assert len(rfp_notifications._buffer) == before

            discarded = RfpTicket(ticket_id=str(uuid.uuid4()), status="discarded")
            session.add(discarded)
            result = IntakeRun(
                status="discarded",
                processing_failed=False,
                error_code=None,
                phi_detected=False,
                compliance_review_required=False,
                raw_pdf_path=None,
            )
            rfp_service._apply_run(session, discarded, result)
            session.refresh(discarded)
            assert discarded.rfp_id is None
            assert len(rfp_notifications._buffer) == before


def test_backfill_assigns_one_id_to_classified_rows_only() -> None:
    with TestClient(app):
        engine = get_engine()
        classified_id = str(uuid.uuid4())
        discarded_id = str(uuid.uuid4())
        analyzing_id = str(uuid.uuid4())
        with Session(engine) as session:
            session.add(RfpTicket(ticket_id=classified_id, status="intake_complete"))
            session.add(RfpTicket(ticket_id=discarded_id, status="discarded"))
            session.add(RfpTicket(ticket_id=analyzing_id, status="analyzing"))
            session.commit()
        _backfill_classified_rfp_ids(engine)
        with Session(engine) as session:
            classified = session.get(RfpTicket, classified_id)
            discarded = session.get(RfpTicket, discarded_id)
            analyzing = session.get(RfpTicket, analyzing_id)
            assert classified is not None and classified.rfp_id is not None
            uuid.UUID(classified.rfp_id)
            assert classified.rfp_id != classified.ticket_id
            stored = classified.rfp_id
            assert discarded is not None and discarded.rfp_id is None
            assert analyzing is not None and analyzing.rfp_id is None
        _backfill_classified_rfp_ids(engine)
        with Session(engine) as session:
            again = session.get(RfpTicket, classified_id)
            assert again is not None and again.rfp_id == stored

        metadata_ticket_id = str(uuid.uuid4())
        with Session(engine) as session:
            session.add(RfpTicket(ticket_id=metadata_ticket_id, status="analyzing"))
            session.add(RfpMetadata(ticket_id=metadata_ticket_id, departments_needed=["revenue"]))
            session.commit()
        _backfill_classified_rfp_ids(engine)
        with Session(engine) as session:
            stored_metadata = session.get(RfpTicket, metadata_ticket_id)
            assert stored_metadata is not None and stored_metadata.rfp_id is not None
