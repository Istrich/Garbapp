"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.rag_contract import (
    DEFAULT_LOCAL_QDRANT_URL,
    DEFAULT_QDRANT_COLLECTION,
    EMBEDDING_MODEL,
)

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime configuration for the API."""

    model_config = SettingsConfigDict(
        env_prefix="GARBAGE_",
        env_file=(
            _BACKEND_DIR / ".env",
            _REPO_ROOT / ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str = Field(default="INFO")

    cors_origins: str = Field(
        default="*",
        description="Comma-separated list of origins, or * for any",
    )

    zip_db_path: Path | None = Field(
        default=None,
        description="SQLite DB path; defaults to <repo>/data/zip_codes.db",
    )

    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "GARBAGE_OPENAI_API_KEY"),
    )
    qdrant_url: str | None = Field(
        default=DEFAULT_LOCAL_QDRANT_URL,
        validation_alias=AliasChoices("QDRANT_URL", "GARBAGE_QDRANT_URL"),
        description="REST URL Qdrant; по умолчанию локальный хост",
    )
    qdrant_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("QDRANT_API_KEY", "GARBAGE_QDRANT_API_KEY"),
    )

    openai_vision_model: str = Field(default="gpt-4o")
    openai_verdict_model: str = Field(default="gpt-4o")
    qdrant_collection: str = Field(default=DEFAULT_QDRANT_COLLECTION)
    embedding_model: str = Field(default=EMBEDDING_MODEL)
    rag_top_k: int = Field(default=6, ge=1, le=25)

    admin_api_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GARBAGE_ADMIN_API_TOKEN", "ADMIN_API_TOKEN"),
        description="Токен для POST/GET /admin/* (заголовок X-Admin-Token или Admin-Token)",
    )

    @field_validator(
        "zip_db_path",
        "openai_api_key",
        "qdrant_url",
        "qdrant_api_key",
        "admin_api_token",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value

    def cors_allow_origins(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw == "*":
            return ["*"]
        return [part.strip() for part in raw.split(",") if part.strip()]

    @property
    def resolved_zip_db_path(self) -> Path:
        if self.zip_db_path is not None:
            return Path(self.zip_db_path).expanduser().resolve()
        return (_REPO_ROOT / "data" / "zip_codes.db").resolve()


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton for dependency injection."""
    return Settings()
