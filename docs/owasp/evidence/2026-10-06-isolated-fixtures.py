"""Valid synthetic inventory, incident, and RFP requests against temporary stores.

The FastAPI routers and services are the application code. The database files,
the RFP completion function, and the approval checkpoint are substitutes.
The script prints statuses and field names. It does not print credentials,
tokens, or response text.
"""

from __future__ import annotations

import os
import secrets
import sys
import tempfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[3] / "services" / "api"
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

TEMP_ROOT = Path(tempfile.mkdtemp(prefix="healthcore-iso-"))
SQLITE_PATH = TEMP_ROOT / "app.db"
TINY_PATH = TEMP_ROOT / "auth.json"
CHECKPOINT_PATH = TEMP_ROOT / "approvals.sqlite"
PASSWORD = secrets.token_urlsafe(18)

os.environ["DATABASE_URL"] = f"sqlite:///{SQLITE_PATH.resolve().as_posix()}"
os.environ["TINYDB_PATH"] = str(TINY_PATH)
os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import get_engine, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from app.rfp_models import DepartmentSection, RfpMetadata, RfpTicket, utc_now  # noqa: E402
from app.services import rfp_service  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()
reset_engine_for_tests()

CLINICAL_NEEDLES = (
    "patient name",
    "diagnosis",
    "medication",
    "mrn",
    "social security",
    "date of birth",
)
COMMERCIAL = "Pricing is quoted in USD for the occupational health program and the twelve month term."


def _clinical(payload: object) -> bool:
    text = str(payload).lower()
    return any(needle in text for needle in CLINICAL_NEEDLES)


def _keys(response: object) -> str:
    body = response.json()
    if isinstance(body, dict):
        return ",".join(sorted(body))
    return type(body).__name__


def _login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    print("LOGIN", email.split("@")[0], response.status_code, "TOKEN_PRESENT", "access_token" in response.json())
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_ticket() -> None:
    now = utc_now()
    ticket = RfpTicket(
        ticket_id="ticket-iso",
        status="under_evaluation",
        created_at=now,
        updated_at=now,
        part3_handoff={
            "ticket_id": "ticket-iso",
            "response_complete": True,
            "currency": "USD",
            "covered_population": "800 employees",
            "sections": [],
        },
    )
    metadata = RfpMetadata(
        ticket_id="ticket-iso",
        client_name="Meridian Manufacturing",
        client_country="US",
        program_type="occupational health",
        covered_population="800 employees",
        departments_needed=["revenue", "clinical", "compliance"],
    )
    with Session(get_engine()) as session:
        session.add(ticket)
        session.add(metadata)
        for department_id in ("revenue", "clinical", "compliance"):
            session.add(
                DepartmentSection(
                    ticket_id="ticket-iso",
                    department_id=department_id,
                    key_aspects={"aspects": ["12-month term"], "open_questions": []},
                    draft_content=COMMERCIAL,
                    evaluation_results={"contains_phi": False, "overall_pass": True},
                    needs_human_review=False,
                )
            )
        session.commit()


print("ISOLATED_DIR_IS_TEMP", str(TEMP_ROOT).startswith(tempfile.gettempdir()))
print("DATABASE_IS_TEMP_SQLITE", os.environ["DATABASE_URL"].endswith(SQLITE_PATH.resolve().as_posix()))
print("OPERATIONAL_PATH_USED", "var/lib/healthcore" in os.environ["DATABASE_URL"] or "var/lib/healthcore" in os.environ["TINYDB_PATH"])

rfp_service.complete_override_fn = lambda _messages: COMMERCIAL
rfp_service.checkpoint_override = CHECKPOINT_PATH

product = {
    "name": "Synthetic gauze roll",
    "sku": "ISO-AUDIT-001",
    "category": "wound_care",
    "unit": "box",
    "country": "US",
    "minimum_stock": 1,
}
incident = {
    "title": "Synthetic pump alarm",
    "description": "Synthetic equipment notice for an isolated fixture.",
    "category": "clinical_equipment",
    "origin": "internal",
    "branch": "central",
    "status": "open",
}

try:
    with TestClient(app) as client:
        anonymous_product = client.post("/inventory/products", json=product)
        print("ANON_PRODUCT", anonymous_product.status_code, "CLINICAL", _clinical(anonymous_product.json()))
        anonymous_incident = client.post("/api/incidents", json=incident)
        print("ANON_INCIDENT", anonymous_incident.status_code)

        first = client.post("/users", json={"email": "iso.a@example.com", "password": PASSWORD, "name": "Iso A"})
        second = client.post("/users", json={"email": "iso.b@example.com", "password": PASSWORD, "name": "Iso B"})
        print("REGISTER", first.status_code, second.status_code)

        owner = _login(client, "iso.a@example.com")
        other = _login(client, "iso.b@example.com")

        created = client.post("/inventory/products", json=product, headers=owner)
        print("AUTH_PRODUCT", created.status_code, "KEYS", _keys(created), "CLINICAL", _clinical(created.json()))
        supply_id = created.json()["id"]
        inbound = client.post(
            "/inventory/orders/inbound",
            json={"supply_id": supply_id, "quantity": 2, "vendor_name": "Synthetic Vendor", "clinic_id": 3},
            headers=owner,
        )
        print("AUTH_INBOUND", inbound.status_code, "KEYS", _keys(inbound), "CLINIC", inbound.json().get("clinic_id"))
        orders = client.get("/inventory/orders", headers=other)
        clinic_ids = sorted({row.get("clinic_id") for row in orders.json()})
        print("OTHER_USER_ORDERS", orders.status_code, "CLINIC_IDS", clinic_ids)

        created_incident = client.post("/api/incidents", json=incident, headers=owner)
        print("AUTH_INCIDENT", created_incident.status_code, "KEYS", _keys(created_incident), "CLINICAL", _clinical(created_incident.json()))
        incident_id = created_incident.json()["id"]
        print("DESCRIPTION_RETAINED", created_incident.json().get("description") == incident["description"])
        other_incident = client.get(f"/api/incidents/{incident_id}", headers=other)
        print("OTHER_USER_INCIDENT", other_incident.status_code, "KEYS", _keys(other_incident))

        _seed_ticket()
        print("RFP_GENERATION_FOR_AUTH", "substituted")
        started = client.post("/rfp/tickets/ticket-iso/approval", headers=owner)
        print("RFP_APPROVAL_START", started.status_code, "KEYS", _keys(started))
        denied = client.post(
            "/rfp/tickets/ticket-iso/approval/revenue",
            json={"decision": "approve"},
            headers=other,
        )
        print("RFP_OTHER_USER", denied.status_code, "DETAIL", denied.json().get("detail"))
finally:
    rfp_service.complete_override_fn = None
    rfp_service.checkpoint_override = None
    get_engine().dispose()
    reset_db_for_tests()
    for path in list(TEMP_ROOT.iterdir()):
        path.unlink(missing_ok=True)
    TEMP_ROOT.rmdir()
    print("TEMP_DB_REMOVED", not TEMP_ROOT.exists())
