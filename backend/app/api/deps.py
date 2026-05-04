"""FastAPI dependency providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.config import Settings, get_settings
from app.services.zip_lookup import ZipLookupService


def require_admin_token(
    settings: Annotated[Settings, Depends(get_settings)],
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    admin_token: Annotated[str | None, Header(alias="Admin-Token")] = None,
) -> None:
    """Проверка секрета для админ-эндпоинтов RAG."""
    expected = (settings.admin_api_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Админ-API отключён: задайте GARBAGE_ADMIN_API_TOKEN или ADMIN_API_TOKEN.",
        )
    got = (x_admin_token or admin_token or "").strip()
    if got != expected:
        raise HTTPException(status_code=403, detail="Недостаточно прав.")


def get_openai_client(request: Request) -> AsyncOpenAI:
    """Shared AsyncOpenAI client from application lifespan."""
    client = getattr(request.app.state, "openai", None)
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Сервис OpenAI не сконфигурирован (нужен OPENAI_API_KEY).",
        )
    return client


def get_qdrant_client(request: Request) -> AsyncQdrantClient:
    """Shared AsyncQdrant client from application lifespan."""
    client = getattr(request.app.state, "qdrant", None)
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Qdrant недоступен (проверьте QDRANT_URL и контейнер).",
        )
    return client


def get_zip_lookup(settings: Annotated[Settings, Depends(get_settings)]) -> ZipLookupService:
    """Provide a zip lookup service bound to configured SQLite path."""
    return ZipLookupService(settings.resolved_zip_db_path)
