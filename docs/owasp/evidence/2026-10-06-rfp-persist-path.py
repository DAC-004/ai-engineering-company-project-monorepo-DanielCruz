"""Store one real generated draft through the RFP service and read it back.

The earlier temporary row was removed, so this script generates once.
It then uses _store_department_outcome and GET /rfp/tickets/{id}.
The draft text is not printed. Stores stay under /tmp.
"""

from __future__ import annotations

import os
import secrets
import sys
import tempfile
from pathlib import Path

ROOT = Path("/opt/healthcore/app")
API_DIR = ROOT / "services" / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API_DIR))

TEMP_ROOT = Path(tempfile.mkdtemp(prefix="healthcore-rfp-path-", dir="/tmp"))
SQLITE_PATH = TEMP_ROOT / "app.db"
os.environ["DATABASE_URL"] = f"sqlite:///{SQLITE_PATH.resolve().as_posix()}"
os.environ["TINYDB_PATH"] = str(TEMP_ROOT / "auth.json")
os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["RAG_MODELS_DIR"] = "/var/lib/healthcore/models"
os.environ["GENERATION_API_KEY"] = ""
os.environ["LLM_API_KEY"] = ""

NEEDLES = (
    "patient name",
    "diagnosis",
    "medication",
    "mrn",
    "social security",
    "date of birth",
)


def _clinical(payload: object) -> bool:
    return any(needle in str(payload).lower() for needle in NEEDLES)


print("TEMP_ROOT_IS_TMP", str(TEMP_ROOT).startswith("/tmp/"))
print("OPERATIONAL_DB_USED", "/var/lib/healthcore" in os.environ["DATABASE_URL"])

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import get_engine, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from app.services import rfp_service  # noqa: E402
from data.pipelines.rfp_intake.generation import complete_local  # noqa: E402
from data.pipelines.rfp_intake.generators import generate_revenue_section  # noqa: E402
from data.pipelines.rfp_intake.phi import screen_generated  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()
reset_engine_for_tests()

metadata = {
    "client_name": "Meridian Manufacturing",
    "client_country": "US",
    "program_type": "occupational health",
    "covered_population": "800 employees",
    "budget_range": "not stated",
    "deadline": "not stated",
    "departments_needed": ["revenue"],
}
raw = generate_revenue_section(metadata, {"aspects": ["12-month term"], "open_questions": []}, complete_local)
screened = screen_generated(raw)
print("GENERATOR", "complete_local")
print("SCREEN_PHI", screened.detected)
print("SCREEN_CHARS", len(screened.text))

import data.pipelines.rfp_intake.generation as rfp_generation  # noqa: E402

if rfp_generation._local_llm is not None:
    rfp_generation._local_llm.close()
    rfp_generation._local_llm = None

try:
    with TestClient(app) as client:
        password = secrets.token_urlsafe(18)
        created_user = client.post(
            "/users",
            json={"email": "rfp.path@example.com", "password": password, "name": "Rfp Path"},
        )
        login = client.post("/auth/login", data={"username": "rfp.path@example.com", "password": password})
        print("REGISTER", created_user.status_code, "LOGIN", login.status_code)
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        with Session(get_engine()) as session:
            ticket = rfp_service.create_ticket(session)
            ticket_id = ticket.ticket_id
        rfp_service._store_department_outcome(
            ticket_id,
            {
                "department_id": "revenue",
                "draft_content": screened.text,
                "evaluation_results": {"contains_phi": screened.detected, "overall_pass": not screened.detected},
                "needs_human_review": screened.detected,
            },
        )
        print("PERSISTENCE", "_store_department_outcome")
        response = client.get(f"/rfp/tickets/{ticket_id}", headers=headers)
        body = response.json()
        sections = body.get("sections") or []
        section = sections[0] if sections else {}
        print("RESPONSE_STATUS", response.status_code)
        print("RESPONSE_PATH", "GET /rfp/tickets/{ticket_id}")
        print("TICKET_KEYS", ",".join(sorted(body)))
        print("SECTION_KEYS", ",".join(sorted(section)))
        print("SECTION_COUNT", len(sections))
        print("RESPONSE_DRAFT_CHARS", len(section.get("draft_content") or ""))
        print("RESPONSE_DRAFT_MATCHES_SCREENED_LENGTH", len(section.get("draft_content") or "") == len(screened.text))
        print("TICKET_PHI_DETECTED", body.get("phi_detected"))
        evaluation = section.get("evaluation_results") or {}
        print("SECTION_CONTAINS_PHI", evaluation.get("contains_phi"))
        print("RESPONSE_CLINICAL", _clinical(section.get("draft_content")))
        print("NEEDS_HUMAN_REVIEW", section.get("needs_human_review"))
finally:
    get_engine().dispose()
    reset_db_for_tests()
    for path in sorted(TEMP_ROOT.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            path.rmdir()
    TEMP_ROOT.rmdir()
    print("TEMP_REMOVED", not TEMP_ROOT.exists())
