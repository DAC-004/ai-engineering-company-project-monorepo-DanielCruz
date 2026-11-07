"""API pytest: isolated Qdrant for non-live runs and AUTH-088 identity fixtures."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Do not import federated_isolation here. That module rewrites storage, seed,
# and live-endpoint env at import. Shared collection of login/RFP/other API
# tests must keep the baseline eager-broker setting below and their own
# DATABASE_URL/TINYDB_PATH handling. Federated pre-import isolation lives in
# tests/test_federated_auth.py, which imports federated_isolation first.

# Set before test modules import app.main so lifespan does not open live Redis.
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "1"

TEST_PASSWORD = "SecurePass1!"
TEST_EMAIL = "alice@healthcore.com"

# AUTH-088 modules use the shared client fixture; RFP and other suites set DATABASE_URL at import.
_AUTH_IDENTITY_TEST_FILES = frozenset(
    {
        "test_login.py",
        "test_me.py",
        "test_register.py",
        "test_token.py",
        "test_roles_permissions.py",
        "test_password_reset.py",
        "test_rfp_demonstration_accounts.py",
        "test_provision_personal_admin.py",
        "test_federated_auth.py",
        "test_onboarding_routes.py",
    }
)


def _use_runtime_qdrant() -> bool:
    return os.getenv("HEALTHCORE_USE_RUNTIME_QDRANT", "").strip() == "1" or os.getenv(
        "PART2_LIVE_RAG_EVAL", ""
    ).strip() == "1"


@pytest.fixture(autouse=True)
def isolate_embedded_qdrant(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Send non-live API tests to a throwaway store so they cannot wipe the knowledge index."""
    from shared.healthcore_rag.qdrant import close_qdrant_client

    close_qdrant_client()
    if _use_runtime_qdrant():
        yield
        close_qdrant_client()
        return

    module_file = getattr(request.module, "__file__", None)
    iso_root = os.environ.get("FEDERATED_ISO_ROOT", "").strip()
    if (
        module_file
        and Path(module_file).name == "test_federated_auth.py"
        and iso_root
    ):
        isolated = Path(iso_root) / "cases" / request.node.name / "qdrant"
        isolated.mkdir(parents=True, exist_ok=True)
    else:
        isolated = tmp_path_factory.mktemp("qdrant")
    monkeypatch.setenv("QDRANT_PATH", str(isolated))
    monkeypatch.delenv("QDRANT_URL", raising=False)
    monkeypatch.setattr("shared.healthcore_rag.config.QDRANT_PATH", str(isolated))
    monkeypatch.setattr("shared.healthcore_rag.config.QDRANT_URL", "")
    yield
    close_qdrant_client()


@pytest.fixture(autouse=True)
def isolated_identity_store(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Path | None, None, None]:
    """Point TinyDB and SQL inventory at temp files; never touch services/api/data/."""
    module_file = getattr(request.module, "__file__", None)
    if module_file is None or Path(module_file).name not in _AUTH_IDENTITY_TEST_FILES:
        yield None
        return

    from app.core.config import get_settings
    from app.database import close_db as close_suppliers_db
    from app.db.database import reset_engine_for_tests
    from app.db.tinydb import reset_db_for_tests

    module_name = Path(module_file).name
    iso_root = os.environ.get("FEDERATED_ISO_ROOT", "").strip()
    if module_name == "test_federated_auth.py" and iso_root:
        case_root = Path(iso_root) / "cases" / request.node.name
        case_root.mkdir(parents=True, exist_ok=True)
        db_path = case_root / "auth.json"
        inventory_db = case_root / "inventory.db"
        suppliers_path = case_root / "suppliers.json"
        incident_data = case_root / "incident-data"
        incident_data.mkdir(parents=True, exist_ok=True)
    else:
        db_path = tmp_path / "auth.json"
        inventory_db = tmp_path / "inventory.db"
        suppliers_path = tmp_path / "suppliers.json"
        incident_data = tmp_path / "incident-data"
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-32chars!!!!")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("TINYDB_PATH", str(db_path))
    monkeypatch.setenv("SUPPLIERS_DB_PATH", str(suppliers_path))
    monkeypatch.setenv("INCIDENT_DATA_DIR", str(incident_data))
    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite:///{inventory_db.resolve().as_posix()}",
    )
    close_suppliers_db()
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    monkeypatch.setenv("RESEND_FROM_EMAIL", "HealthCore <onboarding@resend.dev>")
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://localhost:3000")
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "1")
    monkeypatch.delenv("PLATFORM_SEED_PASSWORD", raising=False)
    monkeypatch.delenv("RFP_DEMONSTRATION_PASSWORD", raising=False)
    if module_name == "test_federated_auth.py":
        monkeypatch.setenv("FEDERATED_OIDC_MODE", "synthetic")
        monkeypatch.setenv("MICROSOFT_CLIENT_ID", "test-client")
        monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("MICROSOFT_TENANT_ID", "test-tenant")
        monkeypatch.setenv(
            "OAUTH_REDIRECT_URI",
            "http://localhost:3000/auth/callback/microsoft",
        )
    get_settings.cache_clear()
    reset_engine_for_tests()
    reset_db_for_tests()
    yield db_path
    close_suppliers_db()
    reset_db_for_tests()
    reset_engine_for_tests()
    get_settings.cache_clear()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_user():
    """Create an active user and linked Profile through application services."""
    from app.schemas.user import UserCreate, UserRole
    from app.services import profile_service, user_service

    user = user_service.create_user(
        UserCreate(email=TEST_EMAIL, password=TEST_PASSWORD, name="Alice"),
        role=UserRole.employee,
    )
    profile_service.create_profile(user_id=user.id, name="Alice")
    return user


@pytest.fixture
def inactive_user(seeded_user):
    """Deactivate via the user service; this is test setup, not a /users CRUD test."""
    from app.schemas.user import UserUpdate
    from app.services import user_service

    updated = user_service.update_user(seeded_user.id, UserUpdate(is_active=False))
    assert updated is not None
    return updated
