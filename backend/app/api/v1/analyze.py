"""Vision + RAG analyze endpoint."""

from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.api.deps import (
    get_openai_client,
    get_qdrant_client,
    get_settings,
    get_zip_lookup,
)
from app.config import Settings
from app.schemas.analyze import AnalyzeResponse
from app.services.analysis_pipeline import ALLOWED_IMAGE_TYPES, run_analyze
from app.services.postal_district import resolve_zip_or_district
from app.services.zip_lookup import ZipLookupService

LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/analyze", tags=["analyze"])

MAX_IMAGE_BYTES = 15 * 1024 * 1024


def _resolve_mime(upload: UploadFile) -> str:
    mime = (upload.content_type or "").split(";")[0].strip().lower()
    if mime in ALLOWED_IMAGE_TYPES:
        return mime
    name = (upload.filename or "").lower()
    if name.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if name.endswith(".png"):
        return "image/png"
    if name.endswith(".webp"):
        return "image/webp"
    raise HTTPException(
        status_code=415,
        detail="Поддерживаются только изображения JPEG, PNG или WebP.",
    )


@router.post(
    "",
    response_model=AnalyzeResponse,
    summary="Двухэтапный анализ отходов (Vision → Qdrant → вердикт)",
)
async def analyze_waste(
    image: Annotated[UploadFile, File(description="Фото предмета")],
    settings: Annotated[Settings, Depends(get_settings)],
    openai_client: Annotated[AsyncOpenAI, Depends(get_openai_client)],
    qdrant_client: Annotated[AsyncQdrantClient, Depends(get_qdrant_client)],
    lookup: Annotated[ZipLookupService, Depends(get_zip_lookup)],
    zip_code: Annotated[str, Form(description="Японский индекс 7 цифр (приоритет над district_id)")] = "",
    district_id: Annotated[str, Form(description="district_id района, если индекс не указан")] = "",
) -> AnalyzeResponse:
    normalized_district = await resolve_zip_or_district(
        zip_code=zip_code,
        district_id=district_id,
        lookup=lookup,
    )
    mime = _resolve_mime(image)
    raw_bytes = await image.read()
    if len(raw_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Файл изображения слишком большой.")

    try:
        return await run_analyze(
            openai=openai_client,
            qdrant=qdrant_client,
            settings=settings,
            image_bytes=raw_bytes,
            mime_type=mime,
            district_id=normalized_district,
        )
    except json.JSONDecodeError:
        LOG.warning("Vision response was not valid JSON")
        raise HTTPException(
            status_code=422,
            detail="Не удалось разобрать ответ модели распознавания.",
        ) from None
    except ValidationError:
        LOG.warning("Vision JSON failed schema validation")
        raise HTTPException(
            status_code=422,
            detail="Ответ модели распознавания не соответствует ожидаемой структуре.",
        ) from None
    except ValueError as exc:
        LOG.warning("Analyze validation error: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except UnexpectedResponse:
        LOG.exception("Qdrant returned an unexpected response")
        raise HTTPException(
            status_code=502,
            detail="Ошибка векторной базы правил (Qdrant).",
        ) from None
    except OpenAIError as exc:
        LOG.warning("OpenAI error: %s", getattr(exc, "message", exc))
        raise HTTPException(
            status_code=502,
            detail="Внешний сервис ИИ временно недоступен.",
        ) from None
