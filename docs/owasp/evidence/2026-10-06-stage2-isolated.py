"""Isolated inventory movements, inactive login, and chat terminal event.

Routers and services are the application. Database files are temporary.
The chat agent in this script is substituted. It is not GGUF output.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

import uvicorn
import websockets
from fastapi import FastAPI

API_DIR = Path(__file__).resolve().parents[3] / "services" / "api"
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

TEMP_ROOT = Path(tempfile.mkdtemp(prefix="healthcore-stage2-"))
SQLITE_PATH = TEMP_ROOT / "app.db"
TINY_PATH = TEMP_ROOT / "auth.json"
PASSWORD = secrets.token_urlsafe(18)
os.environ["DATABASE_URL"] = f"sqlite:///{SQLITE_PATH.resolve().as_posix()}"
os.environ["TINYDB_PATH"] = str(TINY_PATH)
os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app.agent.graph import AgentRun  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.database import get_engine, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
from app.routers.chat import router as chat_router  # noqa: E402
from app.services.chat_channel import get_chat_hub, reset_chat_hub_for_tests  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()
reset_engine_for_tests()
reset_chat_hub_for_tests()

NEEDLES = (
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
    return any(needle in text for needle in NEEDLES)


def _keys(response: object) -> str:
    body = response.json()
    if isinstance(body, dict):
        return ",".join(sorted(body))
    if isinstance(body, list) and body and isinstance(body[0], dict):
        return ",".join(sorted(body[0]))
    return type(body).__name__


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


print("ISOLATED_DIR_IS_TEMP", str(TEMP_ROOT).startswith(tempfile.gettempdir()))
print("OPERATIONAL_PATH_USED", "var/lib/healthcore" in os.environ["DATABASE_URL"] or "var/lib/healthcore" in os.environ["TINYDB_PATH"])

capture = _Capture()
logging.getLogger().addHandler(capture)
auth_logger = logging.getLogger("app.routers.auth")
auth_logger.addHandler(capture)

try:
    with TestClient(app) as client:
        owner_row = client.post("/users", json={"email": "iso.move@example.com", "password": PASSWORD, "name": "Iso Move"})
        other_row = client.post("/users", json={"email": "iso.other@example.com", "password": PASSWORD, "name": "Iso Other"})
        print("REGISTER", owner_row.status_code, other_row.status_code)
        owner_login = client.post("/auth/login", data={"username": "iso.move@example.com", "password": PASSWORD})
        other_login = client.post("/auth/login", data={"username": "iso.other@example.com", "password": PASSWORD})
        print("LOGIN", owner_login.status_code, other_login.status_code, "TOKEN_PRESENT", "access_token" in owner_login.json())
        owner = {"Authorization": f"Bearer {owner_login.json()['access_token']}"}
        other = {"Authorization": f"Bearer {other_login.json()['access_token']}"}
        owner_id = owner_row.json()["id"]

        product = client.post(
            "/inventory/products",
            json={
                "name": "Synthetic gauze roll",
                "sku": "ISO-MOVE-001",
                "category": "wound_care",
                "unit": "box",
                "country": "US",
                "minimum_stock": 1,
            },
            headers=owner,
        )
        print("AUTH_PRODUCT", product.status_code, "KEYS", _keys(product), "CLINICAL", _clinical(product.json()))
        supply_id = product.json()["id"]
        inbound = client.post(
            "/inventory/orders/inbound",
            json={"supply_id": supply_id, "quantity": 4, "vendor_name": "Synthetic Vendor", "clinic_id": 3},
            headers=owner,
        )
        print("AUTH_INBOUND", inbound.status_code, "KEYS", _keys(inbound), "CLINIC", inbound.json().get("clinic_id"))
        outbound = client.post(
            "/inventory/orders/outbound",
            json={
                "supply_id": supply_id,
                "quantity": 1,
                "consumption_type": "clinical_use",
                "department": "primary_care",
                "clinic_id": 3,
            },
            headers=owner,
        )
        print("AUTH_OUTBOUND", outbound.status_code, "KEYS", _keys(outbound), "CLINICAL", _clinical(outbound.json()))
        orders = client.get("/inventory/orders", headers=other)
        order_types = sorted({row.get("order_type") for row in orders.json()})
        clinic_ids = sorted({row.get("clinic_id") for row in orders.json() if row.get("supply_sku") == "ISO-MOVE-001"})
        print("OTHER_USER_ORDERS", orders.status_code, "ORDER_TYPES", order_types, "SYNTHETIC_CLINIC_IDS", clinic_ids)

        incident = {
            "title": "Synthetic pump alarm",
            "description": "Synthetic equipment notice for an isolated fixture.",
            "category": "clinical_equipment",
            "origin": "internal",
            "branch": "central",
            "status": "open",
        }
        created_incident = client.post("/api/incidents", json=incident, headers=owner)
        print("AUTH_INCIDENT", created_incident.status_code, "KEYS", _keys(created_incident), "CLINICAL", _clinical(created_incident.json()))
        other_incident = client.get(f"/api/incidents/{created_incident.json()['id']}", headers=other)
        print("OTHER_USER_INCIDENT", other_incident.status_code)

        bad = client.post("/auth/login", data={"username": "iso.move@example.com", "password": "wrong-password"})
        print("BAD_PASSWORD", bad.status_code, "DETAIL", bad.json().get("detail"))
        before = len(capture.messages)
        deactivated = client.put(f"/users/{owner_id}", json={"is_active": False}, headers=owner)
        print("DEACTIVATE", deactivated.status_code, "ACTIVE", deactivated.json().get("is_active") if deactivated.status_code == 200 else None)
        inactive = client.post("/auth/login", data={"username": "iso.move@example.com", "password": PASSWORD})
        print("INACTIVE_LOGIN", inactive.status_code, "DETAIL", inactive.json().get("detail"))
        new_messages = capture.messages[before:]
        print("INACTIVE_LOG_COUNT", len(new_messages))
        print("INACTIVE_LOG_HAS_PASSWORD", any(PASSWORD in message for message in new_messages))
        print("AUTH_LOGGER_HAS_FILE_HANDLER", any(isinstance(handler, logging.FileHandler) for handler in auth_logger.handlers))

        table_names = sorted(SQLModel.metadata.tables)
        print("SQL_TABLES", ",".join(table_names))
        from app.db.tinydb import get_db

        tiny = get_db()
        print("TINY_TABLES", ",".join(sorted(tiny.tables())))
        print("TINY_INCIDENT_COUNT", len(tiny.table("incidents")))
        print("RESPONSE_CLINICAL", _clinical([product.json(), inbound.json(), outbound.json(), created_incident.json()]))

    import app.agent.graph as graph_module

    graph_module.checkpoint_database_path = lambda: TEMP_ROOT / "checkpoints" / "support_agent.sqlite"
    graph_module.trace_directory = lambda: TEMP_ROOT / "traces"
    import app.agent.memory_store as memory_module

    memory_module.memory_database_path = lambda: TEMP_ROOT / "memory" / "operational.sqlite"
    for directory in (
        TEMP_ROOT / "checkpoints",
        TEMP_ROOT / "traces",
        TEMP_ROOT / "memory",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    def _substituted_agent(question: str, *, thread_id: str | None = None, **_kwargs: object) -> AgentRun:
        return AgentRun(
            answer=COMMERCIAL,
            error="",
            trace_id="substituted-trace",
            thread_id=thread_id or "",
        )

    graph_module.run_support_agent = _substituted_agent
    import app.services.chat_channel as chat_channel

    chat_channel.run_support_agent = _substituted_agent
    print("CHAT_GENERATION", "substituted")

    from app.core.security import create_access_token
    from app.schemas.user import UserCreate, UserRole
    from app.services import user_service

    chat_user = user_service.create_user(
        UserCreate(email="iso.chat@example.com", password=PASSWORD),
        role=UserRole.user,
    )
    token = create_access_token(subject=chat_user.id)
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = int(probe.getsockname()[1])
    probe.close()
    application = FastAPI()
    application.include_router(chat_router)
    server = uvicorn.Server(uvicorn.Config(application, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.2):
                break
        except OSError:
            time.sleep(0.05)

    async def _chat() -> list[str]:
        names: list[str] = []
        url = f"ws://127.0.0.1:{port}/ws/chat/stage2-session"
        async with websockets.connect(url) as connection:
            await connection.send(json.dumps({"event": "auth", "data": {"token": token}}))
            snapshot = json.loads(await connection.recv())
            names.append(snapshot["event"])
            await connection.send(
                json.dumps(
                    {
                        "event": "user_message",
                        "data": {"session_id": "stage2-session", "text": "State the twelve month commercial term."},
                    }
                )
            )
            end = time.time() + 15
            while time.time() < end:
                event = json.loads(await connection.recv())
                names.append(event["event"])
                if event["event"] == "generation_completed":
                    print("TERMINAL_KEYS", ",".join(sorted(event.get("data", {}))))
                    break
        return names

    import asyncio

    event_names = asyncio.run(_chat())
    print("CHAT_EVENTS", ",".join(event_names))
    print("CHAT_REACHED_TERMINAL", event_names[-1] == "generation_completed" if event_names else False)
    session = get_chat_hub().get_session("stage2-session")
    roles = [message.role for message in session.messages] if session is not None else []
    statuses = [message.status for message in session.messages] if session is not None else []
    print("STORED_MESSAGE_ROLES", ",".join(roles))
    print("STORED_MESSAGE_STATUSES", ",".join(statuses))
    print("STORED_CHAT_CLINICAL", _clinical([message.text for message in session.messages]) if session is not None else None)
    print("STORED_CHAT_CHARS", sum(len(message.text) for message in session.messages) if session is not None else 0)
    server.should_exit = True
    thread.join(5)
finally:
    reset_chat_hub_for_tests()
    get_engine().dispose()
    reset_db_for_tests()
    for path in sorted(TEMP_ROOT.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            path.rmdir()
    TEMP_ROOT.rmdir()
    print("TEMP_DB_REMOVED", not TEMP_ROOT.exists())
