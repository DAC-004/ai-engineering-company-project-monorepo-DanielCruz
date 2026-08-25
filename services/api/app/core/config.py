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


@lru_cache
def get_settings() -> Settings:
    return Settings()
