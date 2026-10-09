"""API coverage for Part 3 approval. Generation is the injected complete_fn."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

_owns_database = not os.environ.get("DATABASE_URL", "").startswith("sqlite")
if _owns_database:
    _tmpdir = tempfile.mkdtemp(prefix="rfp-approval-")
    _sqlite_path = (Path(_tmpdir) / "rfp.db").resolve().as_posix()
    os.environ["DATABASE_URL"] = f"sqlite:///{_sqlite_path}"
    os.environ["TINYDB_PATH"] = str(Path(_tmpdir) / "auth.json")
os.environ.setdefault("SECRET_KEY", "rfp-approval-test-secret-key-32")
os.environ.setdefault("RFP_DEMONSTRATION_PASSWORD", "rfp-approval-test-password")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("JWT_ALGORITHM", "HS256")

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import get_engine, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from app.rfp_models import DepartmentSection, RfpFinalDocument, RfpMetadata, RfpTicket, utc_now  # noqa: E402
from app.services import rfp_service  # noqa: E402
from app.services.rfp_demonstration_accounts import demonstration_password  # noqa: E402

get_settings.cache_clear()
if _owns_database:
    reset_db_for_tests()
    reset_engine_for_tests()

REVENUE = "Pricing is quoted in USD for the occupational health program and the twelve month term."
CLINICAL = "Clinical Operations can staff the occupational health program at the stated clinics."
COMPLIANCE = "The compliance section includes a Business Associate Agreement clause for this US client."


def _complete(messages: list[dict[str, str]]) -> str:
    system = messages[0]["content"]
    if "Revenue Cycle" in system:
        return REVENUE
    if "Clinical Operations" in system:
        return CLINICAL
    return COMPLIANCE


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    login = client.post("/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _seed_ticket() -> str:
    now = utc_now()
    ticket = RfpTicket(
        ticket_id="ticket-api",
        status="under_evaluation",
        created_at=now,
        updated_at=now,
        part3_handoff={
            "ticket_id": "ticket-api",
            "response_complete": True,
            "currency": "USD",
            "covered_population": "800 employees",
            "sections": [],
        },
    )
    metadata = RfpMetadata(
        ticket_id="ticket-api",
        client_name="Meridian Manufacturing",
        client_country="US",
        program_type="occupational health",
        covered_population="800 employees",
        departments_needed=["revenue", "clinical", "compliance"],
    )
    drafts = {"revenue": REVENUE, "clinical": CLINICAL, "compliance": COMPLIANCE}
    with Session(get_engine()) as session:
        session.add(ticket)
        session.add(metadata)
        for department_id, draft in drafts.items():
            session.add(
                DepartmentSection(
                    ticket_id="ticket-api",
                    department_id=department_id,
                    key_aspects={"aspects": [], "open_questions": []},
                    draft_content=draft,
                    evaluation_results={"contains_phi": False, "overall_pass": True},
                    needs_human_review=False,
                )
            )
        session.commit()
    return "ticket-api"


def test_approval_route_binds_the_owner_and_stores_the_document(tmp_path: Path) -> None:
    rfp_service.complete_override_fn = _complete
    rfp_service.checkpoint_override = tmp_path / "approvals.sqlite"
    try:
        with TestClient(app) as client:
            ticket_id = _seed_ticket()
            password = demonstration_password()
            revenue = _login(client, "rfp.revenue.demonstration@healthcore.com", password)
            clinical = _login(client, "rfp.clinical.demonstration@healthcore.com", password)
            compliance = _login(client, "rfp.compliance.demonstration@healthcore.com", password)
            missing = client.get(f"/rfp/tickets/{ticket_id}/final-document", headers=revenue)
            assert missing.status_code == 404

            started = client.post(f"/rfp/tickets/{ticket_id}/approval", headers=revenue)
            assert started.status_code == 202
            assert started.json()["status"] == "waiting_for_approval"
            again = client.post(f"/rfp/tickets/{ticket_id}/approval", headers=revenue)
            assert again.status_code == 202

            client.post(
                "/users",
                json={"email": "rfp-other@example.com", "password": "validpass1", "name": "Other Account"},
            )
            other = _login(client, "rfp-other@example.com", "validpass1")
            forbidden = client.post(
                f"/rfp/tickets/{ticket_id}/approval/revenue",
                headers=other,
                json={"decision": "approve"},
            )
            assert forbidden.status_code == 403

            invalid = client.post(
                f"/rfp/tickets/{ticket_id}/approval/revenue",
                headers=revenue,
                json={"decision": "hold"},
            )
            assert invalid.status_code == 422
            missing_note = client.post(
                f"/rfp/tickets/{ticket_id}/approval/revenue",
                headers=revenue,
                json={"decision": "reject"},
            )
            assert missing_note.status_code == 422

            for headers, department_id in (
                (clinical, "clinical"),
                (revenue, "revenue"),
                (compliance, "compliance"),
            ):
                decided = client.post(
                    f"/rfp/tickets/{ticket_id}/approval/{department_id}",
                    headers=headers,
                    json={"decision": "approve"},
                )
                assert decided.status_code == 200

            loaded = client.get(f"/rfp/tickets/{ticket_id}", headers=revenue)
            assert loaded.status_code == 200
            body = loaded.json()
            assert body["status"] == "done"
            by_department = {section["department_id"]: section for section in body["sections"]}
            assert by_department["revenue"]["approver"] == "Tom Callahan"
            assert by_department["clinical"]["approver"] == "Dr. Marcus Reid"
            assert by_department["compliance"]["approver"] == "Claire Whitfield"
            assert by_department["revenue"]["submitted_by_user_id"]
            document = client.get(f"/rfp/tickets/{ticket_id}/final-document", headers=revenue)
            assert document.status_code == 200
            stored = document.json()
            assert set(stored) == {"ticket_id", "sections", "currency", "generated_at"}
            assert stored["currency"] == "USD"
            assert stored["ticket_id"] == ticket_id
            with Session(get_engine()) as session:
                row = session.get(RfpFinalDocument, ticket_id)
                assert row is not None
                ticket = session.get(RfpTicket, ticket_id)
                assert ticket is not None
                assert ticket.status == "done"
    finally:
        rfp_service.complete_override_fn = None
        rfp_service.checkpoint_override = None
