"""Disposable federated-test process isolation. Import before any app module.

Does not import app.*, TinyDB, SQLModel, or FastAPI. Shared API conftest must
not import this module: eager apply would rewrite storage and live flags for
every API collection. The focused federated launch command should set
FEDERATED_ISO_ROOT first; this module fills any gap for a federated-only
pytest invocation so collection cannot fall through to live services/api/data
or port 8000.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ISO_ROOT_ENV = "FEDERATED_ISO_ROOT"
FEDERATED_TEST_MODULE = "test_federated_auth.py"

_LIVE_UNSET_NAMES = (
    "PLATFORM_SEED_PASSWORD",
    "RFP_DEMONSTRATION_PASSWORD",
    "AUTH03_TEST_RECIPIENT",
    "PART2_LIVE_CHAT_WS",
    "PART2_LIVE_RAG_EVAL",
    "PART2_LIVE_GATED_GENERATION",
    "HEALTHCORE_USE_RUNTIME_QDRANT",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "MCP_AGENT_ACCESS_TOKEN",
    "MCP_AGENT_CLIENT_SECRET",
    "MCP_AGENT_CLIENT_ID",
    "GENERATION_API_KEY",
    "LLM_API_KEY",
    "EMBEDDING_API_KEY",
    "RESEND_API_KEY",
)

# pytest options whose following token is a value, not a test path.
_PYTEST_VALUE_OPTIONS = {
    "-k",
    "-m",
    "-p",
    "-o",
    "-n",
    "--tb",
    "--maxfail",
    "--basetemp",
    "--confcutdir",
    "--rootdir",
    "--override-ini",
}


def isolation_root() -> Path:
    return Path(os.environ[ISO_ROOT_ENV])


def apply_storage_paths(root: Path) -> dict[str, str]:
    """Create run-owned auth/link/audit, SQL, supplier, incident, and Qdrant paths."""
    root.mkdir(parents=True, exist_ok=True)
    collection = root / "collection"
    incident = collection / "incident-data"
    qdrant = collection / "qdrant"
    incident.mkdir(parents=True, exist_ok=True)
    qdrant.mkdir(parents=True, exist_ok=True)
    auth = collection / "auth.json"
    inventory = collection / "inventory.db"
    suppliers = collection / "suppliers.json"
    mapping = {
        "TINYDB_PATH": str(auth),
        "SUPPLIERS_DB_PATH": str(suppliers),
        "INCIDENT_DATA_DIR": str(incident),
        "DATABASE_URL": f"sqlite:///{inventory.resolve().as_posix()}",
        "QDRANT_PATH": str(qdrant),
    }
    for name, value in mapping.items():
        os.environ[name] = value
    return mapping


def clear_live_endpoint_and_seed_settings() -> None:
    for name in _LIVE_UNSET_NAMES:
        os.environ.pop(name, None)


def apply_synthetic_non_live_configuration() -> None:
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "1"
    os.environ["FEDERATED_OIDC_MODE"] = "synthetic"
    os.environ["MICROSOFT_CLIENT_ID"] = "test-client"
    os.environ["MICROSOFT_CLIENT_SECRET"] = "test-secret"
    os.environ["MICROSOFT_TENANT_ID"] = "test-tenant"
    os.environ["OAUTH_REDIRECT_URI"] = "http://localhost:3000/auth/callback/microsoft"
    os.environ["SECRET_KEY"] = "test-secret-key-32chars!!!!"
    os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
    os.environ["JWT_ALGORITHM"] = "HS256"
    os.environ["FRONTEND_BASE_URL"] = "http://localhost:3000"
    os.environ["RESEND_FROM_EMAIL"] = "HealthCore <onboarding@resend.dev>"
    # Unused loopback ports: not the preserved 8000/6379 listeners.
    os.environ["TELEMETRY_ENDPOINT"] = "http://127.0.0.1:9/telemetry/events"
    os.environ["REDIS_URL"] = "redis://127.0.0.1:1/15"


def _is_federated_node(item: str) -> bool:
    path = item.split("::", 1)[0].replace("\\", "/")
    return Path(path).name == FEDERATED_TEST_MODULE


def pytest_file_args(argv: list[str] | None = None) -> list[str]:
    """Return non-option pytest path args (test files, node ids, or directories)."""
    selected: list[str] = []
    skip_next = False
    tokens = (argv if argv is not None else sys.argv)[1:]
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token == "--":
            continue
        if token in _PYTEST_VALUE_OPTIONS:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        selected.append(token)
    return selected


def is_federated_only_invocation(argv: list[str] | None = None) -> bool:
    """True only when pytest was asked solely for the federated module.

    An empty path list means the default tests/ tree (whole API suite). Mixed
    file lists include unrelated modules. Either case must leave process env
    alone so collection of login, RFP, and other API tests is unchanged.
    """
    selected = pytest_file_args(argv)
    if not selected:
        return False
    return all(_is_federated_node(item) for item in selected)


def ensure_isolated_process() -> Path:
    existing = os.environ.get(ISO_ROOT_ENV, "").strip()
    if existing:
        root = Path(existing)
    else:
        root = Path(tempfile.mkdtemp(prefix="federated-iso-"))
        os.environ[ISO_ROOT_ENV] = str(root)
    apply_storage_paths(root)
    clear_live_endpoint_and_seed_settings()
    apply_synthetic_non_live_configuration()
    return root


def maybe_apply_for_federated_invocation() -> Path | None:
    """Apply disposable storage only for a federated-only pytest process."""
    if not is_federated_only_invocation():
        return None
    return ensure_isolated_process()


maybe_apply_for_federated_invocation()
