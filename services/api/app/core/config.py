"""Environment-backed settings for JWT, TinyDB identity, and Supabase inventory."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TINYDB_PATH = API_DIR / "data" / "auth.json"


class Settings(BaseSettings):
    """Runtime configuration loaded from environment / `.env` (never hard-coded secrets)."""

    model_config = SettingsConfigDict(
        env_file=str(API_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: str = Field(..., alias="SECRET_KEY", min_length=16)
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
        gt=0,
    )
    # Instructor stack: JWT algorithm is environment-configurable; HS256 remains the default.
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM", min_length=1)
    tinydb_path: Path = Field(default=DEFAULT_TINYDB_PATH, alias="TINYDB_PATH")
    # Supabase transaction-pooler URI (or sqlite for isolated tests). Never hard-code credentials.
    database_url: str = Field(..., alias="DATABASE_URL", min_length=1)
    # Capture-phase destination. The stub does not redirect; Phase 3 will reuse this name.
    telemetry_endpoint: str = Field(
        default="http://localhost:8000/telemetry/events",
        alias="TELEMETRY_ENDPOINT",
        min_length=1,
    )
    # Celery broker and result backend. Same Redis instance for API and workers.
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
        min_length=1,
    )
    # Runtime uploads and last-analysis JSON (gitignored via services/api/data/).
    incident_data_dir: Path = Field(
        default=API_DIR / "data",
        alias="INCIDENT_DATA_DIR",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
