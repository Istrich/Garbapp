"""FastAPI dependency providers."""

from __future__ import annotations

import logging
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.config import Settings, get_settings
from app.services.zip_lookup import ZipLookupService

LOG = logging.getLogger(__name__)

_http_basic = HTTPBasic(auto_error=False)


def require_admin_token(
    settings: Annotated[Settings, Depends(get_settings)],
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    admin_token: Annotated[str | None, Header(alias="Admin-Token")] = None,
) -> None:
    """Проверка секрета для админ-эндпоинтов (если не включён HTTP Basic)."""
    expected = (settings.admin_api_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Админ-API отключён: задайте GARBAGE_ADMIN_API_TOKEN или ADMIN_API_TOKEN.",
        )
    got = (x_admin_token or admin_token or "").strip()
    if not secrets.compare_digest(got.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=403, detail="Недостаточно прав.")


def _admin_basic_pair_ok(
    settings: Settings,
    credentials: HTTPBasicCredentials | None,
) -> None:
    """Проверка пары HTTP Basic; при ошибке — 401 с WWW-Authenticate."""
    user = (settings.admin_http_user or "").strip()
    password = (settings.admin_http_password or "").strip()
    has_u = bool(user)
    has_p = bool(password)
    if has_u ^ has_p:
        raise HTTPException(
            status_code=503,
            detail=(
                "Некорректная настройка админки: задайте оба параметра "
                "ADMIN_HTTP_USER и ADMIN_HTTP_PASSWORD (или ни одного — тогда только токен)."
            ),
        )
    if not (has_u and has_p):
        return
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Требуется HTTP Basic (логин и пароль).",
            headers={"WWW-Authenticate": 'Basic realm="Garbage Admin"'},
        )
    u_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        user.encode("utf-8"),
    )
    p_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        password.encode("utf-8"),
    )
    if not (u_ok and p_ok):
        LOG.warning("Admin HTTP Basic: неверная пара логин/пароль")
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль.",
            headers={"WWW-Authenticate": 'Basic realm="Garbage Admin"'},
        )


def require_admin_page_access(
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_http_basic)],
) -> None:
    """
    Защита **страницы** ``GET /admin`` (и редиректа ``/admin/prompts``).

    HTTP Basic включается только если заданы **оба** логин и пароль в окружении.
    Если не заданы — HTML отдаётся без авторизации (как раньше); доступ к API
    по-прежнему через ``require_admin_access`` (токен или Basic).
    """
    user = (settings.admin_http_user or "").strip()
    password = (settings.admin_http_password or "").strip()
    if not user and not password:
        return
    _admin_basic_pair_ok(settings, credentials)


def require_admin_access(
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_http_basic)],
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    admin_token: Annotated[str | None, Header(alias="Admin-Token")] = None,
) -> None:
    """
    Доступ к ``/api/v1/admin/*``.

    - Если заданы **оба** ``ADMIN_HTTP_USER`` и ``ADMIN_HTTP_PASSWORD`` — только **HTTP Basic**.
    - Иначе — заголовок ``X-Admin-Token`` / ``Admin-Token`` и секрет в настройках.
    """
    user = (settings.admin_http_user or "").strip()
    password = (settings.admin_http_password or "").strip()
    has_u = bool(user)
    has_p = bool(password)
    if has_u ^ has_p:
        raise HTTPException(
            status_code=503,
            detail=(
                "Некорректная настройка админки: задайте оба параметра "
                "ADMIN_HTTP_USER и ADMIN_HTTP_PASSWORD (или ни одного — тогда только токен)."
            ),
        )
    if has_u and has_p:
        _admin_basic_pair_ok(settings, credentials)
        return

    require_admin_token(settings, x_admin_token, admin_token)


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
