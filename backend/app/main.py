"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.api.deps import require_admin_page_access
from app.api.v1.router import api_router
from app.config import get_settings
from app.logging_setup import configure_logging
from app.paths import REPO_ROOT

LOG = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_MINIAPP_DIR = REPO_ROOT / "telegram-miniapp"

_QDRANT_PROBE_ATTEMPTS = 8
_QDRANT_PROBE_DELAY_S = 2.0


def _qdrant_api_key_for_scheme(api_key_raw: str | None, url: str) -> str | None:
    """Не передаём api-key по незащищённому HTTP без явного разрешения (убирает UserWarning клиента)."""
    key = (api_key_raw or "").strip() or None
    if not key:
        return None
    if url.startswith("https://"):
        return key
    allow_http = os.getenv("GARBAGE_QDRANT_HTTP_API_KEY", "").strip().lower() in ("1", "true", "yes")
    if url.startswith("http://") and not allow_http:
        LOG.warning(
            "QDRANT_API_KEY не отправляется по HTTP без GARBAGE_QDRANT_HTTP_API_KEY=1 "
            "(локальный Qdrant в docker-compose часто без ключа). Для keyed Qdrant по HTTP "
            "(например контейнер→контейнер) включите переменную.",
        )
        return None
    return key


async def _probe_qdrant_collections(client: AsyncQdrantClient) -> Any:
    """Несколько попыток: Qdrant в Docker может отдавать 503, пока не поднялся REST."""
    last_exc: BaseException | None = None
    for attempt in range(1, _QDRANT_PROBE_ATTEMPTS + 1):
        try:
            return await client.get_collections()
        except Exception as exc:
            last_exc = exc
            LOG.warning(
                "Проверка Qdrant %s/%s не удалась: %s",
                attempt,
                _QDRANT_PROBE_ATTEMPTS,
                exc,
            )
            if attempt < _QDRANT_PROBE_ATTEMPTS:
                await asyncio.sleep(_QDRANT_PROBE_DELAY_S)
    assert last_exc is not None
    raise last_exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared SDK clients for Vision/RAG orchestration."""
    settings = get_settings()

    api_key = (settings.openai_api_key or "").strip()
    app.state.openai = AsyncOpenAI(api_key=api_key) if api_key else None

    q_url = (settings.qdrant_url or "").strip().rstrip("/")
    parsed_q = urlparse(q_url)
    if parsed_q.hostname == "qdrant":
        LOG.warning(
            "QDRANT_URL указывает на хост «qdrant» — это имя доступно только контейнерам Docker "
            "внутри compose-сети. Если uvicorn запущен на вашей машине, замените URL на "
            "http://127.0.0.1:6333 (порт 6333 должен быть проброшен из контейнера Qdrant).",
        )

    qdrant_key = _qdrant_api_key_for_scheme(settings.qdrant_api_key, q_url)

    app.state.qdrant = (
        AsyncQdrantClient(
            url=q_url,
            api_key=qdrant_key,
            timeout=60,
            check_compatibility=False,
        )
        if q_url
        else None
    )

    if app.state.openai is None:
        LOG.warning(
            "OPENAI_API_KEY отсутствует — эндпоинт POST /api/v1/analyze недоступен до настройки.",
        )
    if app.state.qdrant is None:
        LOG.warning(
            "QDRANT_URL отсутствует — эндпоинт POST /api/v1/analyze недоступен до настройки.",
        )
    elif app.state.qdrant is not None:
        try:
            cols = await _probe_qdrant_collections(app.state.qdrant)
            names = [c.name for c in cols.collections]
            LOG.info(
                "Qdrant готов: %s (коллекций: %s). Целевая `%s` %s.",
                q_url,
                len(names),
                settings.qdrant_collection,
                "найдена" if settings.qdrant_collection in names else "не найдена — выполните init_vector_db.py",
            )
        except Exception as exc:
            LOG.warning(
                "AsyncQdrantClient создан (%s), но проверка доступности не удалась после повторов: %s",
                q_url,
                exc,
            )

    yield

    if app.state.openai is not None:
        await app.state.openai.close()
    if app.state.qdrant is not None:
        await app.state.qdrant.close()


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Garbage App API",
        description="Backend для классификации отходов по районам Японии",
        version="0.1.0",
        lifespan=lifespan,
    )

    origins = settings.cors_allow_origins()
    # Starlette forbids credentials=True together with wildcard origins.
    allow_credentials = "*" not in origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    _STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="static",
    )

    if _MINIAPP_DIR.is_dir():
        app.mount(
            "/miniapp",
            StaticFiles(directory=str(_MINIAPP_DIR), html=True),
            name="miniapp",
        )
    else:
        LOG.warning("Mini App directory not found: %s", _MINIAPP_DIR)

    @app.get(
        "/admin",
        tags=["system"],
        include_in_schema=False,
        dependencies=[Depends(require_admin_page_access)],
    )
    async def admin_ui() -> FileResponse:
        """Простая админ-страница для загрузки PDF и запуска ingest."""
        html_path = _STATIC_DIR / "admin.html"
        if not html_path.is_file():
            raise HTTPException(status_code=404, detail="admin.html не найден")
        return FileResponse(
            html_path,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.get(
        "/admin/prompts",
        tags=["system"],
        include_in_schema=False,
        dependencies=[Depends(require_admin_page_access)],
    )
    async def prompts_legacy_redirect() -> RedirectResponse:
        """Старая ссылка: промпты перенесены во вкладку на /admin."""
        return RedirectResponse(
            url="/admin?tab=prompts",
            status_code=307,
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Liveness probe for orchestrators."""
        return {"status": "ok"}

    LOG.info("ZIP DB path: %s", settings.resolved_zip_db_path)
    return app


app = create_app()
