"""Format full log records for inactive login and a generation failure.

getMessage() is not the check. Formatter.format includes exc_info when set.
The marker must not appear in the formatted record or the trace file.
"""

from __future__ import annotations

import io
import logging
import os
import secrets
import sys
import tempfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[3] / "services" / "api"
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

TEMP_ROOT = Path(tempfile.mkdtemp(prefix="healthcore-logfmt-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TEMP_ROOT / 'app.db').resolve().as_posix()}"
os.environ["TINYDB_PATH"] = str(TEMP_ROOT / "auth.json")
os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

from fastapi.testclient import TestClient  # noqa: E402

from app.agent.graph import GRAPH_EXECUTION_FAILED, run_support_agent  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db.database import get_engine, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()
reset_engine_for_tests()

MARKER = "SECRET_EXCEPTION_DETAIL"
FORMATTER = logging.Formatter("%(name)s %(levelname)s %(message)s")
PASSWORD = secrets.token_urlsafe(18)


class _FullCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[str, str, bool]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.rows.append((record.name, FORMATTER.format(record), record.exc_info is not None))


def _summarize(label: str, rows: list[tuple[str, str, bool]], secret: str) -> None:
    blob = "\n".join(text for _name, text, _has_exc in rows)
    names = ",".join(sorted({name for name, _text, _has_exc in rows})) or "none"
    print(f"{label}_RECORD_COUNT", len(rows))
    print(f"{label}_LOGGER_NAMES", repr(names))
    print(f"{label}_EXC_INFO_SET", sum(1 for _name, _text, has_exc in rows if has_exc))
    print(f"{label}_FORMATTED_HAS_SECRET", secret in blob)
    print(f"{label}_FORMATTED_HAS_TRACEBACK", "Traceback (most recent call last)" in blob)


login_capture = _FullCapture()
for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "app.routers.auth", "fastapi"):
    logger = logging.getLogger(name)
    logger.addHandler(login_capture)
    logger.setLevel(logging.INFO)

print("OPERATIONAL_PATH_USED", "var/lib/healthcore" in os.environ["TINYDB_PATH"])
try:
    with TestClient(app) as client:
        created = client.post(
            "/users",
            json={"email": "inactive.format@example.com", "password": PASSWORD, "name": "Inactive Format"},
        )
        login = client.post(
            "/auth/login",
            data={"username": "inactive.format@example.com", "password": PASSWORD},
        )
        token = login.json()["access_token"]
        user_id = created.json()["id"]
        headers = {"Authorization": f"Bearer {token}"}
        deactivated = client.put(f"/users/{user_id}", json={"is_active": False}, headers=headers)
        before = len(login_capture.rows)
        inactive = client.post(
            "/auth/login",
            data={"username": "inactive.format@example.com", "password": PASSWORD},
        )
        print("DEACTIVATE", deactivated.status_code, "ACTIVE", deactivated.json().get("is_active"))
        print("INACTIVE_STATUS", inactive.status_code, "DETAIL", inactive.json().get("detail"))
        window = login_capture.rows[before:]
        _summarize("INACTIVE", window, PASSWORD)
        print("INACTIVE_DETAIL_IN_FORMATTED", "Inactive user" in "\n".join(text for _name, text, _has_exc in window))

    import app.agent.graph as graph_module
    import data.pipelines.rag as rag

    failure_capture = _FullCapture()
    stderr_buffer = io.StringIO()
    stderr_handler = logging.StreamHandler(stderr_buffer)
    stderr_handler.setFormatter(FORMATTER)
    graph_logger = logging.getLogger("app.agent.graph")
    existing = [type(handler).__name__ for handler in graph_logger.handlers]
    print("GRAPH_LOGGER_HANDLERS_BEFORE", ",".join(existing) or "none")
    graph_logger.addHandler(failure_capture)
    graph_logger.addHandler(stderr_handler)
    graph_logger.setLevel(logging.ERROR)
    graph_logger.propagate = False

    def _retrieve(*_args: object, **_kwargs: object) -> list[dict[str, str]]:
        return [{"source_document": "synthetic-note", "text": "Synthetic commercial note."}]

    def _fail(_question: str, _context: list[dict[str, str]]) -> str:
        raise RuntimeError(MARKER)

    rag.retrieve = _retrieve
    rag.generate_answer = _fail
    trace_dir = TEMP_ROOT / "traces"
    trace_dir.mkdir()
    raised = False
    try:
        run_support_agent(
            "How long does an internal referral take?",
            checkpoint_path=TEMP_ROOT / "agent.sqlite",
            trace_dir=trace_dir,
        )
    except RuntimeError:
        raised = True
    print("FAILURE_RAISED", raised)
    print("APPLICATION_CALL", "logger.error without exc_info")
    _summarize("FAILURE", failure_capture.rows, MARKER)
    stderr_text = stderr_buffer.getvalue()
    print("STDERR_STREAM_HAS_SECRET", MARKER in stderr_text)
    print("STDERR_STREAM_HAS_TRACEBACK", "Traceback (most recent call last)" in stderr_text)
    print("STDERR_STREAM_HAS_FAILURE_SENTENCE", "graph execution failed" in stderr_text)
    trace_files = list(trace_dir.glob("*.json"))
    trace_text = trace_files[0].read_text(encoding="utf-8") if trace_files else ""
    print("TRACE_FILE_COUNT", len(trace_files))
    print("TRACE_ERROR_CODE", GRAPH_EXECUTION_FAILED in trace_text)
    print("TRACE_HAS_SECRET", MARKER in trace_text)
    print("TRACE_HAS_TRACEBACK", "Traceback (most recent call last)" in trace_text)
    source = Path(graph_module.__file__).read_text(encoding="utf-8")
    error_call = source.split("logger.error(", 1)[1].split(")", 1)[0]
    print("SOURCE_ERROR_PASSES_EXC_INFO", "exc_info" in error_call)

    route_capture = _FullCapture()
    route_logger = logging.getLogger("app.routers.agent")
    route_logger.addHandler(route_capture)
    route_logger.setLevel(logging.ERROR)
    route_logger.propagate = False
    graph_module.trace_directory = lambda: trace_dir
    graph_module.checkpoint_database_path = lambda: TEMP_ROOT / "route-agent.sqlite"
    with TestClient(app) as route_client:
        route_response = route_client.post(
            "/agent/query",
            json={"question": "How long does an internal referral take?"},
        )
    print("ROUTE_STATUS", route_response.status_code)
    print("ROUTE_DETAIL_IS_GENERIC", route_response.json().get("detail") == "The knowledge assistant could not generate an answer right now.")
    print("ROUTE_BODY_HAS_SECRET", MARKER in route_response.text)
    _summarize("ROUTE", route_capture.rows, MARKER)
    print("ROUTE_CALL", "logger.exception")
    route_traces = list(trace_dir.glob("*.json"))
    route_blob = "\n".join(path.read_text(encoding="utf-8") for path in route_traces)
    print("ALL_TRACE_COUNT", len(route_traces))
    print("ALL_TRACE_HAS_SECRET", MARKER in route_blob)
    print("ALL_TRACE_HAS_TRACEBACK", "Traceback (most recent call last)" in route_blob)
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
