"""Shared AUTH-088 fixtures: isolated TinyDB, JWT settings, and TestClient."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

# Set JWT settings before app modules cache Settings from a developer .env.
os.environ["SECRET_KEY"] = "test-secret-key-32chars!!!!"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["JWT_ALGORITHM"] = "HS256"

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.tinydb import reset_db_for_tests
from app.main import app
from app.schemas.user import UserCreate, UserRole, UserUpdate
from app.services import profile_service, user_service

TEST_PASSWORD = "SecurePass1!"
TEST_EMAIL = "alice@healthcore.com"


@pytest.fixture(autouse=True)
def isolated_identity_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    """Point TinyDB at a temp file so tests never touch services/api/data/."""
    db_path = tmp_path / "auth.json"
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-32chars!!!!")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("TINYDB_PATH", str(db_path))
    get_settings.cache_clear()
    reset_db_for_tests()
    yield db_path
    reset_db_for_tests()
    get_settings.cache_clear()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded_user():
    """Create an active user and linked Profile through application services."""
    user = user_service.create_user(
        UserCreate(email=TEST_EMAIL, password=TEST_PASSWORD, name="Alice"),
        role=UserRole.user,
    )
    profile_service.create_profile(user_id=user.id, name="Alice")
    return user


@pytest.fixture
def inactive_user(seeded_user):
    """Deactivate via the user service; this is test setup, not a /users CRUD test."""
    updated = user_service.update_user(seeded_user.id, UserUpdate(is_active=False))
    assert updated is not None
    return updated
