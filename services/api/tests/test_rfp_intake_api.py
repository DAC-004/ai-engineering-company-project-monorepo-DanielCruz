"""API intake tests on a temporary SQLite file.

SQLite exercises the code path. It is not the PostgreSQL/Supabase criterion.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

_tmpdir = tempfile.mkdtemp(prefix="rfp-intake-")
_sqlite_path = (Path(_tmpdir) / "rfp.db").resolve().as_posix()
os.environ["SECRET_KEY"] = "rfp-intake-test-secret-key-32"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["TINYDB_PATH"] = str(Path(_tmpdir) / "auth.json")
os.environ["DATABASE_URL"] = f"sqlite:///{_sqlite_path}"
os.environ["NLTK_DATA"] = str(REPO_ROOT / "data" / "process" / "nltk_data")

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import get_engine, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from app.rfp_models import DepartmentSection, RfpMetadata, RfpTicket  # noqa: E402
from app.services import rfp_service  # noqa: E402
from data.pipelines.rfp_intake.runner import IntakeRun, process_pdf  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()
reset_engine_for_tests()

PATIENT_NAME = "Alex Example"
PATIENT_DIAGNOSIS = "example condition"
STORAGE_DIR = Path(_tmpdir) / "raw"


def _pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    lines = escaped.split("\n")
    commands = ["BT", "/F1 12 Tf"]
    y_position = 720
    for line in lines:
        commands.append(f"1 0 0 1 72 {y_position} Tm ({line}) Tj")
        y_position -= 16
    commands.append("ET")
    stream = "\n".join(commands).encode("latin1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj\n",
        (
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        ),
        b"4 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    cursor = 9
    offsets = []
    body = bytearray(b"%PDF-1.4\n")
    for obj in objects:
        offsets.append(cursor)
        body.extend(obj)
        cursor += len(obj)
    xref_at = cursor
    xref = [b"xref\n0 6\n0000000000 65535 f \n"]
    for offset in offsets:
        xref.append(f"{offset:010d} 00000 n \n".encode())
    body.extend(b"".join(xref))
    body.extend(
        f"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    )
    return bytes(body)


def _complete(messages: list[dict[str, str]]) -> str:
    system = messages[0]["content"]
    user = messages[-1]["content"]
    if "classifier agent" in system:
        if "MedFlow" in user:
            return json.dumps({"decision": "discard", "reason_code": "not_healthcore_rfp"})
        return json.dumps({"decision": "accept", "reason_code": "healthcore_rfp"})
    if "orchestrator agent" in system:
        if "Thames Valley" in user:
            return json.dumps(
                {
                    "client_name": "Thames Valley University",
                    "client_country": "UK",
                    "program_type": "referral network",
                    "covered_population": "about 3,000 main-campus students",
                    "deadline": "about 25 days, around August 28",
                    "budget_range": None,
                    "unknown_departments": [],
                    "extracts": {
                        "revenue": "No budget amount is stated.",
                        "clinical": "about 3,000 main-campus students and a satellite clinic.",
                        "compliance": "UK GDPR.",
                    },
                }
            )
        return json.dumps(
            {
                "client_name": "Meridian Manufacturing, Inc.",
                "client_country": "US",
                "program_type": "on-site occupational health and corporate wellness",
                "covered_population": "800 employees",
                "deadline": "August 23, 2026",
                "budget_range": None,
                "unknown_departments": ["Facilities"],
                "extracts": {
                    "revenue": "12-month term. No budget amount is stated.",
                    "clinical": "800 employees in Austin.",
                    "compliance": "Business Associate Agreement.",
                },
            }
        )
    if "revenue worker" in system:
        return json.dumps(
            {"aspects": ["12-month term."], "open_questions": ["Budget was not stated."]}
        )
    if "clinical worker" in system:
        return json.dumps({"aspects": ["Staffing follows the stated population."], "open_questions": []})
    if "compliance worker" in system:
        return json.dumps({"aspects": ["Regulatory review is required."], "open_questions": []})
    if "synthesizer agent" in system:
        if "Patient name:" in user or PATIENT_NAME in user:
            return json.dumps(
                {
                    "summary": f"Patient name: {PATIENT_NAME}. Diagnosis: {PATIENT_DIAGNOSIS}.",
                    "unresolved_disagreements": [],
                }
            )
        return json.dumps(
            {
                "summary": "Ask Tom Callahan, Dr. Marcus Reid, and Claire Whitfield.",
                "unresolved_disagreements": [],
            }
        )
    raise AssertionError("unexpected agent role")


def _auth_header(client: TestClient) -> dict[str, str]:
    client.post(
        "/users",
        json={"email": "rfp-intake@example.com", "password": "validpass1", "name": "RFP Tester"},
    )
    login = client.post(
        "/auth/login",
        data={"username": "rfp-intake@example.com", "password": "validpass1"},
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_upload_returns_analyzing_then_reaches_intake_complete(caplog) -> None:
    caplog.set_level(logging.ERROR)
    rfp_service.complete_override_fn = _complete
    rfp_service.storage_override = STORAGE_DIR
    try:
        with TestClient(app) as client:
            headers = _auth_header(client)
            created = client.post(
                "/rfp/tickets",
                headers=headers,
                files={"file": ("request.pdf", _pdf("Meridian Manufacturing requests occupational health."), "application/pdf")},
            )
            assert created.status_code == 202
            body = created.json()
            assert body["status"] == "analyzing"
            ticket_id = body["ticket_id"]
            loaded = client.get(f"/rfp/tickets/{ticket_id}", headers=headers)
    finally:
        rfp_service.complete_override_fn = None
        rfp_service.storage_override = None

    assert loaded.status_code == 200
    payload = loaded.json()
    assert payload["status"] == "intake_complete"
    assert payload["processing_failed"] is False
    assert payload["metadata"]["client_country"] == "US"
    assert payload["metadata"]["budget_range"] is None
    assert payload["metadata"]["covered_population"] == "800 employees"
    assert {section["department_id"] for section in payload["sections"]} == {
        "revenue",
        "clinical",
        "compliance",
    }
    assert payload["part2_handoff"]["ticket_id"] == ticket_id
    assert "USD" in payload["synthesizer_summary"]
    revenue = next(section for section in payload["sections"] if section["department_id"] == "revenue")
    assert "Budget was not stated." in revenue["key_aspects"]["open_questions"]
    assert any("Facilities" in question for question in revenue["key_aspects"]["open_questions"])
    with Session(get_engine()) as session:
        stored = session.get(RfpTicket, ticket_id)
        metadata = session.exec(select(RfpMetadata).where(RfpMetadata.ticket_id == ticket_id)).one()
        sections = session.exec(select(DepartmentSection).where(DepartmentSection.ticket_id == ticket_id)).all()
    assert stored is not None
    assert stored.status == "intake_complete"
    assert stored.part2_handoff["ticket_id"] == ticket_id
    assert metadata.budget_range is None
    assert metadata.covered_population == "800 employees"
    assert len(sections) == 3


def test_vendor_pitch_is_discarded_without_changing_another_ticket() -> None:
    rfp_service.complete_override_fn = _complete
    rfp_service.storage_override = STORAGE_DIR
    try:
        with TestClient(app) as client:
            headers = _auth_header(client)
            accepted = client.post(
                "/rfp/tickets",
                headers=headers,
                files={"file": ("ok.pdf", _pdf("Thames Valley University requests a referral partnership."), "application/pdf")},
            )
            discarded = client.post(
                "/rfp/tickets",
                headers=headers,
                files={"file": ("pitch.pdf", _pdf("MedFlow wants to sell an EHR."), "application/pdf")},
            )
            accepted_body = client.get(f"/rfp/tickets/{accepted.json()['ticket_id']}", headers=headers).json()
            discarded_body = client.get(f"/rfp/tickets/{discarded.json()['ticket_id']}", headers=headers).json()
    finally:
        rfp_service.complete_override_fn = None
        rfp_service.storage_override = None

    assert accepted_body["status"] == "intake_complete"
    assert accepted_body["metadata"]["deadline"] == "about 25 days, around August 28"
    assert accepted_body["metadata"]["covered_population"] == "about 3,000 main-campus students"
    assert "GBP" in accepted_body["synthesizer_summary"]
    assert discarded_body["status"] == "discarded"
    assert discarded_body["part2_handoff"] is None


def _assert_absent(blob: str) -> None:
    assert PATIENT_NAME not in blob
    assert PATIENT_DIAGNOSIS not in blob


def test_input_phi_is_not_stored_logged_or_returned(caplog) -> None:
    caplog.set_level(logging.ERROR)
    source = f"Clinical case summary\nPatient name: {PATIENT_NAME}\nDiagnosis: {PATIENT_DIAGNOSIS}\n"
    rfp_service.complete_override_fn = _complete
    rfp_service.storage_override = STORAGE_DIR
    try:
        with TestClient(app) as client:
            headers = _auth_header(client)
            created = client.post(
                "/rfp/tickets",
                headers=headers,
                files={"file": ("case.pdf", _pdf(source), "application/pdf")},
            )
            ticket_id = created.json()["ticket_id"]
            loaded = client.get(f"/rfp/tickets/{ticket_id}", headers=headers)
    finally:
        rfp_service.complete_override_fn = None
        rfp_service.storage_override = None

    payload = loaded.json()
    _assert_absent(json.dumps(payload))
    assert payload["phi_detected"] is True
    assert payload["compliance_review_required"] is True
    assert payload["raw_pdf_path"] is None
    assert not (STORAGE_DIR / f"{ticket_id}.pdf").exists()
    with Session(get_engine()) as session:
        stored = session.get(RfpTicket, ticket_id)
    assert stored is not None
    _assert_absent(json.dumps(stored.model_dump(), default=str))
    _assert_absent(Path(_sqlite_path).read_text(encoding="utf-8", errors="ignore"))
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    _assert_absent(log_text)


def test_generated_phi_is_screened_before_persist(caplog) -> None:
    caplog.set_level(logging.ERROR)

    def leaking_complete(messages: list[dict[str, str]]) -> str:
        if "synthesizer agent" in messages[0]["content"]:
            return json.dumps(
                {
                    "summary": (
                        f"Ask Claire Whitfield about the BAA. Patient name: {PATIENT_NAME}. "
                        f"Diagnosis: {PATIENT_DIAGNOSIS}."
                    ),
                    "unresolved_disagreements": [],
                }
            )
        return _complete(messages)

    rfp_service.complete_override_fn = leaking_complete
    rfp_service.storage_override = STORAGE_DIR
    try:
        with TestClient(app) as client:
            headers = _auth_header(client)
            created = client.post(
                "/rfp/tickets",
                headers=headers,
                files={"file": ("clean.pdf", _pdf("Meridian Manufacturing requests occupational health."), "application/pdf")},
            )
            ticket_id = created.json()["ticket_id"]
            loaded = client.get(f"/rfp/tickets/{ticket_id}", headers=headers)
    finally:
        rfp_service.complete_override_fn = None
        rfp_service.storage_override = None

    payload = loaded.json()
    assert payload["status"] == "intake_complete"
    assert payload["phi_detected"] is True
    _assert_absent(json.dumps(payload))
    with Session(get_engine()) as session:
        stored = session.get(RfpTicket, ticket_id)
    assert stored is not None
    _assert_absent(json.dumps(stored.model_dump(), default=str))
    _assert_absent(Path(_sqlite_path).read_text(encoding="utf-8", errors="ignore"))
    stored_pdf = STORAGE_DIR / f"{ticket_id}.pdf"
    if stored_pdf.exists():
        _assert_absent(stored_pdf.read_text(encoding="latin1", errors="ignore"))
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    _assert_absent(log_text)


def test_missing_model_does_not_mark_the_ticket_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    empty_models = Path(_tmpdir) / "no-such-models"
    empty_models.mkdir(exist_ok=True)
    monkeypatch.setenv("RAG_MODELS_DIR", str(empty_models))
    result = process_pdf(
        _pdf("Meridian Manufacturing requests occupational health."),
        "missing-model",
        complete_fn=None,
        storage_dir=STORAGE_DIR,
    )
    assert result.status == "analyzing"
    assert result.processing_failed is True
    assert result.error_code == "model_asset_missing"
    assert result.handoff is None


def test_intake_complete_is_not_visible_before_sections_and_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = get_engine()
    with Session(engine) as session:
        ticket = rfp_service.create_ticket(session)
        ticket_id = ticket.ticket_id
    seen: list[dict[str, object]] = []
    original_commit = Session.commit

    def spy(self: Session) -> None:
        original_commit(self)
        with Session(engine) as reader:
            row = reader.get(RfpTicket, ticket_id)
            if row is None or row.status != "intake_complete":
                return
            metadata = reader.exec(select(RfpMetadata).where(RfpMetadata.ticket_id == ticket_id)).first()
            sections = list(
                reader.exec(select(DepartmentSection).where(DepartmentSection.ticket_id == ticket_id)).all()
            )
            handoff = row.part2_handoff if isinstance(row.part2_handoff, dict) else None
            seen.append(
                {
                    "has_metadata": metadata is not None and metadata.client_name == "Meridian Manufacturing, Inc.",
                    "section_count": len(sections),
                    "handoff": handoff is not None and handoff.get("ticket_id") == ticket_id,
                }
            )

    monkeypatch.setattr(Session, "commit", spy)
    result = IntakeRun(
        status="intake_complete",
        processing_failed=False,
        error_code=None,
        phi_detected=False,
        compliance_review_required=False,
        raw_pdf_path=None,
        metadata={
            "client_name": "Meridian Manufacturing, Inc.",
            "client_country": "US",
            "departments_needed": ["revenue", "clinical", "compliance"],
        },
        readability={"flesch_kincaid_grade": 13.0, "gunning_fog": 11.0},
        sections=[
            {
                "department_id": "revenue",
                "department_name": "Revenue Cycle",
                "contact_name": "Tom Callahan",
                "aspects": ["No budget amount is stated."],
                "open_questions": ["Budget was not stated."],
            },
            {
                "department_id": "clinical",
                "department_name": "Clinical Operations",
                "contact_name": "Dr. Marcus Reid",
                "aspects": ["Clinic staffed 3 days/week."],
                "open_questions": [],
            },
            {
                "department_id": "compliance",
                "department_name": "Compliance and Data Governance",
                "contact_name": "Claire Whitfield",
                "aspects": ["BAA."],
                "open_questions": [],
            },
        ],
        summary="Ask Tom Callahan for the budget.",
        handoff={"ticket_id": ticket_id, "synthesizer_summary": "Ask Tom Callahan for the budget."},
    )
    with Session(engine) as session:
        stored = session.get(RfpTicket, ticket_id)
        assert stored is not None
        rfp_service._apply_run(session, stored, result)
        rfp_service._apply_run(session, stored, result)

    assert seen
    assert all(
        item == {"has_metadata": True, "section_count": 3, "handoff": True} for item in seen
    )


def test_pipeline_exception_stays_analyzing_without_logging_the_message(caplog) -> None:
    caplog.set_level(logging.ERROR)

    def explode(_messages: list[dict[str, str]]) -> str:
        raise RuntimeError(f"boom {PATIENT_NAME}")

    rfp_service.complete_override_fn = explode
    rfp_service.storage_override = STORAGE_DIR
    try:
        with TestClient(app) as client:
            headers = _auth_header(client)
            created = client.post(
                "/rfp/tickets",
                headers=headers,
                files={"file": ("boom.pdf", _pdf("Meridian Manufacturing request"), "application/pdf")},
            )
            loaded = client.get(f"/rfp/tickets/{created.json()['ticket_id']}", headers=headers)
    finally:
        rfp_service.complete_override_fn = None
        rfp_service.storage_override = None

    assert loaded.json()["status"] == "analyzing"
    assert loaded.json()["processing_failed"] is True
    assert loaded.json()["processing_error_code"] == "pipeline_exception"
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert PATIENT_NAME not in log_text
    assert "boom" not in log_text


def _ready_handoff(ticket_id: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "metadata": {"client_name": "Meridian Manufacturing", "client_country": "US"},
        "sections": [
            {
                "department_id": "revenue",
                "key_aspects": {"aspects": ["Contract term is twelve months."], "open_questions": []},
            },
            {
                "department_id": "clinical",
                "key_aspects": {"aspects": ["Austin clinic capacity."], "open_questions": []},
            },
            {
                "department_id": "compliance",
                "key_aspects": {"aspects": ["Business Associate Agreement clause."], "open_questions": []},
            },
        ],
    }


def test_response_entry_drafts_from_the_handoff_without_parsing_the_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.pipelines.test_rfp_evaluator import PASSING_DRAFT

    def refuse_pdf(*_args, **_kwargs):
        raise AssertionError("Part 2 must not parse the PDF")

    def complete(messages: list[dict[str, str]]) -> str:
        payload = json.loads(messages[-1]["content"])
        department_id = payload["department_id"]
        if department_id == "clinical":
            return PASSING_DRAFT + " Austin clinic capacity covers the stated workforce."
        if department_id == "compliance":
            return PASSING_DRAFT + " The compliance section includes a Business Associate Agreement clause."
        return PASSING_DRAFT

    monkeypatch.setattr("app.services.rfp_service.process_pdf", refuse_pdf)
    monkeypatch.setattr("data.pipelines.rfp_intake.convert.pdf_bytes_to_markdown", refuse_pdf)
    rfp_service.complete_override_fn = complete
    try:
        with TestClient(app) as client:
            headers = _auth_header(client)
            with Session(get_engine()) as session:
                ticket = RfpTicket(
                    ticket_id="ready-ticket-1",
                    status="intake_complete",
                    raw_pdf_path="data/raw/rfp_intake/ready-ticket-1.pdf",
                    part2_handoff=_ready_handoff("ready-ticket-1"),
                )
                session.add(ticket)
                session.commit()
            started = client.post("/rfp/tickets/ready-ticket-1/response", headers=headers)
            loaded = client.get("/rfp/tickets/ready-ticket-1", headers=headers)
    finally:
        rfp_service.complete_override_fn = None

    body = loaded.json()
    assert started.status_code == 202
    assert started.json()["status"] == "drafting"
    assert body["status"] == "under_evaluation"
    assert body["part2_handoff"]["ticket_id"] == "ready-ticket-1"
    assert body["raw_pdf_path"] == "data/raw/rfp_intake/ready-ticket-1.pdf"
    assert body["part3_handoff"]["response_complete"] is True
    assert {section["department_id"] for section in body["sections"]} == {"revenue", "clinical", "compliance"}
    assert all(section["draft_content"] for section in body["sections"])
    assert all(section["evaluation_results"]["overall_pass"] is True for section in body["sections"])
    assert all(section["needs_human_review"] is False for section in body["sections"])


def test_exhausted_revenue_section_sets_ticket_needs_human_review(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.pipelines.test_rfp_evaluator import PASSING_DRAFT

    def refuse_pdf(*_args, **_kwargs):
        raise AssertionError("Part 2 must not parse the PDF")

    def complete(messages: list[dict[str, str]]) -> str:
        payload = json.loads(messages[-1]["content"])
        department_id = payload["department_id"]
        if department_id == "revenue":
            return "This quote uses GBP."
        if department_id == "clinical":
            return PASSING_DRAFT + " Austin clinic capacity covers the stated workforce."
        return PASSING_DRAFT + " The compliance section includes a Business Associate Agreement clause."

    monkeypatch.setattr("app.services.rfp_service.process_pdf", refuse_pdf)
    monkeypatch.setattr("data.pipelines.rfp_intake.convert.pdf_bytes_to_markdown", refuse_pdf)
    rfp_service.complete_override_fn = complete
    try:
        with TestClient(app) as client:
            headers = _auth_header(client)
            with Session(get_engine()) as session:
                session.add(
                    RfpTicket(
                        ticket_id="exhausted-ticket-1",
                        status="intake_complete",
                        part2_handoff=_ready_handoff("exhausted-ticket-1"),
                    )
                )
                session.commit()
            started = client.post("/rfp/tickets/exhausted-ticket-1/response", headers=headers)
            loaded = client.get("/rfp/tickets/exhausted-ticket-1", headers=headers)
    finally:
        rfp_service.complete_override_fn = None

    body = loaded.json()
    sections = {section["department_id"]: section for section in body["sections"]}
    revenue = sections["revenue"]

    assert started.status_code == 202
    assert started.json()["status"] == "drafting"
    assert body["status"] == "needs_human_review"
    assert body["status"] not in {"waiting_for_approval", "done"}
    assert body["part3_handoff"]["response_complete"] is True
    assert [section["department_id"] for section in body["part3_handoff"]["sections"]] == [
        "revenue",
        "clinical",
        "compliance",
    ]
    assert revenue["needs_human_review"] is True
    assert revenue["draft_content"] == "This quote uses GBP."
    assert revenue["evaluation_results"]["overall_pass"] is False
    assert "HC-CURRENCY" in revenue["evaluation_results"]["compliance"]["rule_ids"]
    assert revenue["evaluation_results"]["feedback_for_generator"]
    assert sections["clinical"]["needs_human_review"] is False
    assert sections["clinical"]["evaluation_results"]["overall_pass"] is True
    assert sections["compliance"]["needs_human_review"] is False
    assert sections["compliance"]["evaluation_results"]["overall_pass"] is True
    with TestClient(app) as client:
        headers = _auth_header(client)
        with Session(get_engine()) as session:
            session.add(RfpTicket(ticket_id="discarded-ticket", status="discarded"))
            session.add(
                RfpTicket(
                    ticket_id="analyzing-ticket",
                    status="analyzing",
                    part2_handoff=_ready_handoff("analyzing-ticket"),
                )
            )
            session.commit()
        discarded = client.post("/rfp/tickets/discarded-ticket/response", headers=headers)
        analyzing = client.post("/rfp/tickets/analyzing-ticket/response", headers=headers)
        missing = client.post("/rfp/tickets/missing-ticket/response", headers=headers)

    assert discarded.status_code == 409
    assert discarded.json()["detail"] == "not_intake_complete"
    assert analyzing.status_code == 409
    assert analyzing.json()["detail"] == "not_intake_complete"
    assert missing.status_code == 404


def test_existing_rfp_tables_gain_part2_columns() -> None:
    from sqlalchemy import create_engine, inspect, text

    from app.db.database import _ensure_rfp_response_columns

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE rfp_ticket (ticket_id VARCHAR(36) PRIMARY KEY, status VARCHAR(32))")
        )
        connection.execute(
            text(
                "CREATE TABLE rfp_department_section "
                "(id INTEGER PRIMARY KEY, ticket_id VARCHAR(36), department_id VARCHAR(32))"
            )
        )
    _ensure_rfp_response_columns(engine)
    inspector = inspect(engine)
    ticket_columns = {column["name"] for column in inspector.get_columns("rfp_ticket")}
    section_columns = {column["name"] for column in inspector.get_columns("rfp_department_section")}

    assert "part3_handoff" in ticket_columns
    assert {"draft_content", "evaluation_results", "needs_human_review"} <= section_columns


def test_database_url_quotes_a_reserved_character_in_the_password() -> None:
    from urllib.parse import unquote, urlsplit

    from app.db.database import _normalize_database_url

    raw = "postgresql:postgresql://postgres.project:abc#def@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    normalized = _normalize_database_url(raw)
    parts = urlsplit(normalized)

    assert parts.hostname == "aws-0-us-east-1.pooler.supabase.com"
    assert parts.port == 6543
    assert unquote(parts.password or "") == "abc#def"
    assert "%23" in normalized
    assert parts.path == "/postgres"

    direct = urlsplit(
        _normalize_database_url("postgresql://postgres:secret@db.example.supabase.co:6543/postgres")
    )
    assert direct.hostname == "db.example.supabase.co"
    assert direct.port == 5432


def test_database_url_preserves_valid_ports_and_an_encoded_password() -> None:
    from urllib.parse import urlsplit

    from app.db.database import _normalize_database_url

    direct = urlsplit(
        _normalize_database_url("postgresql://postgres:secret@db.example.supabase.co:5432/postgres")
    )
    pooler = urlsplit(
        _normalize_database_url(
            "postgresql://postgres.project:secret@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
        )
    )
    encoded = _normalize_database_url(
        "postgresql://postgres:abc%23def@db.example.supabase.co:5432/postgres"
    )
    encoded_parts = urlsplit(encoded)

    assert direct.port == 5432
    assert direct.password == "secret"
    assert direct.path == "/postgres"
    assert pooler.hostname == "aws-0-us-east-1.pooler.supabase.com"
    assert pooler.port == 6543
    assert pooler.username == "postgres.project"
    assert pooler.password == "secret"
    assert encoded_parts.port == 5432
    assert encoded_parts.password == "abc%23def"
    assert "%2523" not in encoded
