"""Почтовый индекс Японии → district_id из SQLite (zip_mapping)."""

from __future__ import annotations

import logging
import re
import sqlite3

from fastapi import HTTPException

from app.services.zip_lookup import ZipLookupService, normalize_japanese_zip

LOG = logging.getLogger(__name__)

_DISTRICT_RE = re.compile(r"^[a-z0-9_]{1,64}$")


def normalize_strict_district_id(raw: str) -> str:
    """Латиница / цифры / snake_case, нижний регистр."""
    value = raw.strip().lower()
    if not _DISTRICT_RE.fullmatch(value):
        raise HTTPException(
            status_code=422,
            detail="district_id: только латиница, цифры и подчёркивание (snake_case).",
        )
    return value


async def resolve_zip_or_district(
    *,
    zip_code: str,
    district_id: str,
    lookup: ZipLookupService,
) -> str:
    """
    Если ``zip_code`` непустой — ищем район в ``zip_codes.db`` (приоритет).
    Иначе используем явный ``district_id``.
    """
    zip_raw = zip_code.strip()
    district_raw = district_id.strip()

    if zip_raw:
        normalized_zip = normalize_japanese_zip(zip_raw)
        if len(normalized_zip) != 7:
            raise HTTPException(
                status_code=422,
                detail="Почтовый индекс: ровно 7 цифр (можно с дефисом, например 060-0031).",
            )
        try:
            resolved = await lookup.get_district_id(normalized_zip)
        except FileNotFoundError:
            LOG.exception("ZIP database missing")
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

        if resolved is None:
            # 422: не путать с «нет маршрута» (404) в логах прокси и мониторинга.
            raise HTTPException(
                status_code=422,
                detail=f"Почтовый индекс {normalized_zip} не найден в базе данных.",
            )

        LOG.info("zip_code=%s → district_id=%s", normalized_zip, resolved)
        return normalize_strict_district_id(resolved)

    if district_raw:
        return normalize_strict_district_id(district_raw)

    raise HTTPException(
        status_code=422,
        detail="Укажите почтовый индекс (zip_code) или district_id.",
    )
