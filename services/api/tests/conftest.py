"""API pytest: isolated Qdrant for non-live runs and AUTH-088 identity fixtures."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shared.healthcore_rag.qdrant import close_qdrant_client

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
    }
)


def _use_runtime_qdrant() -> bool:
    return os.getenv("HEALTHCORE_USE_RUNTIME_QDRANT", "").strip() == "1" or os.getenv(
        "PART2_LIVE_RAG_EVAL", ""
    ).strip() == "1"


@pytest.fixture(autouse=True)
def isolate_embedded_qdrant(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    """Send non-live API tests to a throwaway store so they cannot wipe the knowledge index."""
    close_qdrant_client()
    if _use_runtime_qdrant():
        yield
        close_qdrant_client()
        return

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
