"""Exercise POST /knowledge/query when the pipeline raises.

The router name pipeline_query is patched. Retrieval and generation do not run.
Formatter.format is the check. The marker is not printed.
"""

from __future__ import annotations

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

TEMP_ROOT = Path(tempfile.mkdtemp(prefix="healthcore-knowledge-exc-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TEMP_ROOT / 'app.db').resolve().as_posix()}"
os.environ["TINYDB_PATH"] = str(TEMP_ROOT / "auth.json")
os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import get_engine, reset_engine_for_tests  # noqa: E402
from app.db.tinydb import reset_db_for_tests  # noqa: E402
from app.main import app  # noqa: E402
import app.routers.knowledge as knowledge_router  # noqa: E402

get_settings.cache_clear()
reset_db_for_tests()
reset_engine_for_tests()

MARKER = "SECRET_EXCEPTION_DETAIL"
FORMATTER = logging.Formatter("%(name)s %(levelname)s %(message)s")
GENERIC_DETAIL = "The knowledge assistant could not generate an answer right now."


class _FullCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[str, str, bool]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.rows.append((record.name, FORMATTER.format(record), record.exc_info is not None))


print("OPERATIONAL_PATH_USED", "var/lib/healthcore" in os.environ["TINYDB_PATH"])
knowledge_logger = logging.getLogger("app.routers.knowledge")
print(
    "KNOWLEDGE_HANDLERS_BEFORE",
    ",".join(type(handler).__name__ for handler in knowledge_logger.handlers) or "none",
)
print("KNOWLEDGE_PROPAGATE_BEFORE", knowledge_logger.propagate)
capture = _FullCapture()
knowledge_logger.addHandler(capture)
knowledge_logger.setLevel(logging.ERROR)
knowledge_logger.propagate = False


def _fail(_question: str) -> str:
    raise RuntimeError(MARKER)


knowledge_router.pipeline_query = _fail
print("PIPELINE_PATCHED", knowledge_router.pipeline_query is _fail)
try:
    with TestClient(app) as client:
        response = client.post(
            "/knowledge/query",
            json={"question": "How long does an internal referral take?"},
        )
    print("KNOWLEDGE_STATUS", response.status_code)
    print("KNOWLEDGE_DETAIL_IS_GENERIC", response.json().get("detail") == GENERIC_DETAIL)
    print("KNOWLEDGE_BODY_HAS_SECRET", MARKER in response.text)
    blob = "\n".join(text for _name, text, _has_exc in capture.rows)
    names = ",".join(sorted({name for name, _text, _has_exc in capture.rows})) or "none"
    print("KNOWLEDGE_RECORD_COUNT", len(capture.rows))
    print("KNOWLEDGE_LOGGER_NAMES", repr(names))
    print("KNOWLEDGE_EXC_INFO_SET", sum(1 for _name, _text, has_exc in capture.rows if has_exc))
    print("KNOWLEDGE_FORMATTED_HAS_SECRET", MARKER in blob)
    print("KNOWLEDGE_FORMATTED_HAS_TRACEBACK", "Traceback (most recent call last)" in blob)
    print("KNOWLEDGE_CALL", "logger.exception")
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
