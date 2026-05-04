"""Postal code → district endpoints."""

from __future__ import annotations

import logging
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.api.deps import get_zip_lookup
from app.schemas.location import LocationResponse
from app.services.zip_lookup import ZipLookupService, normalize_japanese_zip

LOG = logging.getLogger(__name__)

router = APIRouter(prefix="/location", tags=["location"])


@router.get(
    "/{zip_code}",
    response_model=LocationResponse,
    summary="Определить район по почтовому индексу",
)
async def resolve_location(
    zip_code: Annotated[
        str,
        Path(
            description="Японский почтовый индекс (с дефисом или без)",
            examples=["1600022", "160-0022"],
        ),
    ],
    lookup: Annotated[ZipLookupService, Depends(get_zip_lookup)],
) -> LocationResponse:
    normalized = normalize_japanese_zip(zip_code)
    if len(normalized) != 7:
        raise HTTPException(
            status_code=422,
            detail="Укажите корректный японский почтовый индекс из 7 цифр.",
        )

    try:
        district_id = await lookup.get_district_id(normalized)
    except FileNotFoundError:
        LOG.exception("ZIP database unavailable")
        raise HTTPException(
            status_code=503,
            detail="База почтовых индексов временно недоступна.",
        ) from None
    except sqlite3.Error:
        LOG.exception("SQLite error during zip lookup")
        raise HTTPException(
            status_code=503,
            detail="Ошибка чтения базы почтовых индексов.",
        ) from None

    if district_id is None:
        raise HTTPException(
            status_code=404,
            detail="Индекс не найден в базе данных.",
        )

    return LocationResponse(zip_code=normalized, district_id=district_id)
