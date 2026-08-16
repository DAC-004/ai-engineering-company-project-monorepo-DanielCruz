"""Environment-backed settings for JWT, TinyDB identity, and password-reset email."""

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
