"""Generation-failure and tool-call logging with isolated persistence.

Retrieval and answer generation are patched. persist_trace and
log_tool_invocation are the application functions. A second process reads
the trace file. The invocation logger is not given a file handler.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[3] / "services" / "api"
REPO_ROOT = API_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(API_DIR))

from app.agent.graph import GRAPH_EXECUTION_FAILED, run_support_agent  # noqa: E402

SECRET = "SECRET_EXCEPTION_DETAIL"
TEMP_ROOT = Path(tempfile.mkdtemp(prefix="healthcore-log-"))
TRACE_DIR = TEMP_ROOT / "traces"
TRACE_DIR.mkdir()
CHECKPOINT = TEMP_ROOT / "agent.sqlite"


def _retrieve(*_args: object, **_kwargs: object) -> list[dict[str, str]]:
    return [{"source_document": "synthetic-note", "text": "Synthetic commercial note."}]


def _fail(_question: str, _context: list[dict[str, str]]) -> str:
    raise RuntimeError(SECRET)


import data.pipelines.rag as rag  # noqa: E402

rag.retrieve = _retrieve
rag.generate_answer = _fail

records: list[logging.LogRecord] = []


class _Capture(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        records.append(record)


logger = logging.getLogger("app.agent.graph")
logger.addHandler(_Capture())
logger.setLevel(logging.ERROR)

failed = False
try:
    run_support_agent(
        "How long does an internal referral take?",
        checkpoint_path=CHECKPOINT,
        trace_dir=TRACE_DIR,
    )
except RuntimeError:
    failed = True

print("FAILURE_RAISED", failed)
print("LOG_RECORD_COUNT", len(records))
print("LOG_CONTAINS_SECRET", any(SECRET in record.getMessage() for record in records))
print("LOGGER_HAS_FILE_HANDLER", any(isinstance(handler, logging.FileHandler) for handler in logger.handlers))
trace_files = list(TRACE_DIR.glob("*.json"))
print("TRACE_FILE_COUNT", len(trace_files))
trace_path = trace_files[0]
stored = json.loads(trace_path.read_text(encoding="utf-8"))
print("TRACE_ERROR_IS_FAILURE_CODE", stored.get("error") == GRAPH_EXECUTION_FAILED)
print("TRACE_CONTAINS_SECRET", SECRET in trace_path.read_text(encoding="utf-8"))
print("TRACE_KEYS", ",".join(sorted(stored)))

reader = subprocess.run(
    [
        sys.executable,
        "-c",
        "import json,sys; body=json.load(open(sys.argv[1],encoding='utf-8')); print(body.get('error')); print('SECRET' in json.dumps(body))",
        str(trace_path),
    ],
    check=True,
    capture_output=True,
    text=True,
)
second_error, second_secret = reader.stdout.strip().splitlines()
print("SECOND_PROCESS_ERROR_IS_FAILURE_CODE", second_error == GRAPH_EXECUTION_FAILED)
print("SECOND_PROCESS_HAS_SECRET", second_secret == "True")

invocation_path = REPO_ROOT / "mcps" / "healthcore-tools" / "src" / "healthcore_tools" / "invocation_log.py"
spec = importlib.util.spec_from_file_location("invocation_log_isolated", invocation_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
captured: list[str] = []


class _InvocationCapture(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        captured.append(record.getMessage())


invocation_logger = logging.getLogger(module.INVOCATION_LOGGER_NAME)
invocation_logger.addHandler(_InvocationCapture())
invocation_logger.setLevel(logging.INFO)
module.log_tool_invocation(
    tool="attempt_inventory_modification",
    client="isolated-reader",
    result="inventory_write_forbidden",
)
message = captured[-1]
print(
    "INVOCATION_MESSAGE_HAS_FIELDS",
    "tool=attempt_inventory_modification" in message
    and "client=isolated-reader" in message
    and "result=inventory_write_forbidden" in message,
)
print("INVOCATION_FILE_CREATED", any(TEMP_ROOT.glob("*.log")))
print("CONFIGURE_CO_NAMES", ",".join(sorted(module.configure_invocation_logging.__code__.co_names)))

for path in TEMP_ROOT.rglob("*"):
    if path.is_file():
        path.unlink()
for path in sorted(TEMP_ROOT.rglob("*"), reverse=True):
    if path.is_dir():
        path.rmdir()
TEMP_ROOT.rmdir()
print("TEMP_LOG_REMOVED", not TEMP_ROOT.exists())
