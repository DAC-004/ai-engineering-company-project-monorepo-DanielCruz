"""Real RFP generation and one chat turn, both stored only under /tmp.

complete_local and generate_answer are the application generators.
Retrieval for the chat turn is substituted because Qdrant is not used.
"""

from __future__ import annotations

import asyncio
import gc
import json
import os
import secrets
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path("/opt/healthcore/app")
API_DIR = ROOT / "services" / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API_DIR))

TEMP_ROOT = Path(tempfile.mkdtemp(prefix="healthcore-stage2-", dir="/tmp"))
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
    text = str(payload).lower()
    return any(needle in text for needle in NEEDLES)


print("TEMP_ROOT_IS_TMP", str(TEMP_ROOT).startswith("/tmp/"))
print("OPERATIONAL_DB_USED", "/var/lib/healthcore" in os.environ["DATABASE_URL"] or "/var/lib/healthcore" in os.environ["TINYDB_PATH"])

from sqlmodel import Session, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import get_engine, init_databases, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.rfp_models import DepartmentSection, RfpTicket, utc_now  # noqa: E402
from data.pipelines.rfp_intake.generation import complete_local  # noqa: E402
from data.pipelines.rfp_intake.generators import generate_revenue_section  # noqa: E402
from data.pipelines.rfp_intake.phi import screen_generated  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()
reset_engine_for_tests()
init_databases()

metadata = {
    "client_name": "Meridian Manufacturing",
    "client_country": "US",
    "program_type": "occupational health",
    "covered_population": "800 employees",
    "budget_range": "not stated",
    "deadline": "not stated",
    "departments_needed": ["revenue"],
}
aspects = {"aspects": ["12-month term"], "open_questions": []}
raw = generate_revenue_section(metadata, aspects, complete_local)
screened = screen_generated(raw)
now = utc_now()
with Session(get_engine()) as session:
    session.add(
        RfpTicket(
            ticket_id="ticket-stage2",
            status="under_evaluation",
            created_at=now,
            updated_at=now,
            part3_handoff={"ticket_id": "ticket-stage2", "response_complete": False},
        )
    )
    session.add(
        DepartmentSection(
            ticket_id="ticket-stage2",
            department_id="revenue",
            key_aspects=aspects,
            draft_content=screened.text,
            evaluation_results={"contains_phi": screened.detected, "overall_pass": not screened.detected},
            needs_human_review=screened.detected,
        )
    )
    session.commit()

with Session(get_engine()) as session:
    stored = session.exec(select(DepartmentSection).where(DepartmentSection.ticket_id == "ticket-stage2")).one()
    print("RFP_GENERATION", "complete_local")
    print("STORED_COLUMNS", ",".join(sorted(stored.model_dump().keys())))
    print("STORED_DRAFT_CHARS", len(stored.draft_content or ""))
    print("STORED_PHI_FLAG", bool((stored.evaluation_results or {}).get("contains_phi")))
    print("STORED_REDACTED", "[redacted]" in (stored.draft_content or ""))
    print("STORED_CLINICAL", _clinical(stored.draft_content))
    print("STORED_ROW_COUNT", 1)

import data.pipelines.rfp_intake.generation as rfp_generation  # noqa: E402

if rfp_generation._local_llm is not None:
    rfp_generation._local_llm.close()
    rfp_generation._local_llm = None
gc.collect()

import app.agent.graph as graph_module  # noqa: E402
import app.agent.memory_store as memory_module  # noqa: E402
import data.pipelines.rag as rag  # noqa: E402

for directory in (TEMP_ROOT / "checkpoints", TEMP_ROOT / "traces", TEMP_ROOT / "memory"):
    directory.mkdir(parents=True, exist_ok=True)
graph_module.checkpoint_database_path = lambda: TEMP_ROOT / "checkpoints" / "support_agent.sqlite"
graph_module.trace_directory = lambda: TEMP_ROOT / "traces"
memory_module.memory_database_path = lambda: TEMP_ROOT / "memory" / "operational.sqlite"


def _retrieve(_question: str, **_kwargs: object) -> list[dict[str, str]]:
    return [
        {
            "company": "healthcore",
            "source_document": "synthetic-note",
            "section": "Commercial term",
            "language": "en",
            "chunk_index": 0,
            "text": "Pricing is quoted in USD for the occupational health program and the twelve month term.",
        }
    ]


rag.retrieve = _retrieve
print("CHAT_RETRIEVAL", "substituted")
print("CHAT_GENERATION", "generate_answer")

from app.core.security import create_access_token  # noqa: E402
from app.routers.chat import router as chat_router  # noqa: E402
from app.schemas.user import UserCreate, UserRole  # noqa: E402
from app.services import user_service  # noqa: E402
from app.services.chat_channel import get_chat_hub, reset_chat_hub_for_tests  # noqa: E402

reset_chat_hub_for_tests()
chat_user = user_service.create_user(
    UserCreate(email="stage2.chat@example.com", password=secrets.token_urlsafe(18)),
    role=UserRole.user,
)
token = create_access_token(subject=chat_user.id)
probe = socket.socket()
probe.bind(("127.0.0.1", 0))
port = int(probe.getsockname()[1])
probe.close()

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402

application = FastAPI()
application.include_router(chat_router)
server = uvicorn.Server(uvicorn.Config(application, host="127.0.0.1", port=port, log_level="warning"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
deadline = time.time() + 8
while time.time() < deadline:
    try:
        with socket.create_connection(("127.0.0.1", port), 0.2):
            break
    except OSError:
        time.sleep(0.05)


async def _chat() -> list[str]:
    import websockets

    names: list[str] = []
    url = f"ws://127.0.0.1:{port}/ws/chat/stage2-guest"
    async with websockets.connect(url) as connection:
        await connection.send(json.dumps({"event": "auth", "data": {"token": token}}))
        snapshot = json.loads(await connection.recv())
        names.append(snapshot["event"])
        await connection.send(
            json.dumps(
                {
                    "event": "user_message",
                    "data": {"session_id": "stage2-guest", "text": "State the twelve month commercial term."},
                }
            )
        )
        end = time.time() + 180
        while time.time() < end:
            event = json.loads(await asyncio.wait_for(connection.recv(), timeout=end - time.time()))
            names.append(event["event"])
            if event["event"] in {"generation_completed", "generation_interrupted"}:
                print("TERMINAL_EVENT", event["event"])
                print("TERMINAL_KEYS", ",".join(sorted(event.get("data", {}))))
                break
    return names


event_names = asyncio.run(_chat())
print("CHAT_EVENTS", ",".join(event_names))
session = get_chat_hub().get_session("stage2-guest")
if session is None:
    print("STORED_MESSAGE_COUNT", 0)
else:
    print("STORED_MESSAGE_ROLES", ",".join(message.role for message in session.messages))
    print("STORED_MESSAGE_STATUSES", ",".join(message.status for message in session.messages))
    print("STORED_CHAT_CHARS", sum(len(message.text) for message in session.messages))
    print("STORED_CHAT_CLINICAL", _clinical([message.text for message in session.messages]))
    print("LAST_GENERATION_KEYS", ",".join(sorted(session.last_generation)))
trace_files = list((TEMP_ROOT / "traces").glob("*.json"))
print("TRACE_FILE_COUNT", len(trace_files))
if trace_files:
    stored_trace = json.loads(trace_files[0].read_text(encoding="utf-8"))
    print("TRACE_KEYS", ",".join(sorted(stored_trace)))
    print("TRACE_CLINICAL", _clinical(stored_trace))
print("CHECKPOINT_IS_TEMP", str(graph_module.checkpoint_database_path()).startswith("/tmp/"))
server.should_exit = True
thread.join(5)
rag.release_local_llm()
get_engine().dispose()
reset_db_for_tests()
reset_chat_hub_for_tests()
for path in sorted(TEMP_ROOT.rglob("*"), reverse=True):
    if path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        path.rmdir()
TEMP_ROOT.rmdir()
print("TEMP_REMOVED", not TEMP_ROOT.exists())
