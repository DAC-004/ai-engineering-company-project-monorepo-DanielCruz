"""Environment-backed settings for JWT, TinyDB identity, Supabase inventory, and password-reset email."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
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
    # Supabase transaction-pooler URI (or sqlite for local Docker / tests). Never hard-code credentials.
    database_url: str = Field(..., alias="DATABASE_URL", min_length=1)
    # Capture-phase destination. The stub does not redirect; Phase 3 will reuse this name.
    telemetry_endpoint: str = Field(
        default="http://localhost:8000/telemetry/events",
        alias="TELEMETRY_ENDPOINT",
        min_length=1,
    )
    # Comma-separated browser origins. Docker backoffice uses 3001; tracker workspace uses 3000/3002.
    cors_origins: str = Field(
        default=(
            "http://127.0.0.1:3000,http://localhost:3000,"
            "http://127.0.0.1:3001,http://localhost:3001,"
            "http://127.0.0.1:3002,http://localhost:3002,"
            "http://127.0.0.1:5500,http://localhost:5500,null"
        ),
        alias="CORS_ORIGINS",
        min_length=1,
    )

    # AUTH-03 — Resend transactional email (API key must come from the environment).
    resend_api_key: str | None = Field(default=None, alias="RESEND_API_KEY")
    resend_from_email: str = Field(
        default="HealthCore <onboarding@resend.dev>",
        alias="RESEND_FROM_EMAIL",
        min_length=3,
    )
    frontend_base_url: str = Field(
        default="http://localhost:3000",
        alias="FRONTEND_BASE_URL",
        min_length=1,
    )
    # Allowed AUTH-03 window is 15–60 minutes; default mid-range.
    password_reset_token_expire_minutes: int = Field(
        default=30,
        alias="PASSWORD_RESET_TOKEN_EXPIRE_MINUTES",
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

    @field_validator("password_reset_token_expire_minutes")
    @classmethod
    def validate_reset_token_lifetime(cls, value: int) -> int:
        if value < 15 or value > 60:
            raise ValueError(
                "PASSWORD_RESET_TOKEN_EXPIRE_MINUTES must be between 15 and 60"
            )
        return value

    @field_validator("frontend_base_url")
    @classmethod
    def normalize_frontend_base_url(cls, value: str) -> str:
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
