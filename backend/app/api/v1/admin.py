"""Admin endpoints for RAG storage (PDF upload + ingest pipeline)."""

from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)

from app.api.deps import get_zip_lookup, require_admin_token
from app.config import Settings, get_settings
from app.paths import REPO_ROOT
from app.schemas.admin import AdminIngestAccepted, AdminUploadResponse, AdminZipDbImportResult
from app.schemas.prompts import AnalyzePromptsPayload
from app.services.admin_rag_pipeline import run_full_ingest_pipeline
from app.services.analyze_prompts import load_analyze_prompts, save_analyze_prompts
from app.services.ken_csv_import import load_csv_into_sqlite, lookup_district_id
from app.services.postal_district import normalize_strict_district_id, resolve_zip_or_district
from app.services.zip_lookup import ZipLookupService

LOG = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_token)],
)

_MAX_PDF_BYTES = 35 * 1024 * 1024
_MAX_KEN_CSV_BYTES = 512 * 1024 * 1024
_ALLOWED_KEN_ENCODINGS = frozenset({"shift_jis", "utf-8"})


def _safe_pdf_filename(original: str) -> str:
    stem = Path(original).stem or "rules"
    suffix = Path(original).suffix.lower()
    if suffix != ".pdf":
        suffix = ".pdf"
    cleaned = re.sub(r"[^a-zA-Z0-9._\-]", "_", stem)[:120]
    return f"{cleaned}{suffix}"


def _enqueue_ingest(
    background_tasks: BackgroundTasks,
    settings: Settings,
    normalized: str,
    *,
    recreate: bool,
) -> AdminIngestAccepted:
    async def _ingest_job() -> None:
        try:
            result = await run_full_ingest_pipeline(
                district_id=normalized,
                collection=settings.qdrant_collection,
                recreate_collection=recreate,
            )
            LOG.info("Admin ingest completed: %s", result)
        except Exception:
            LOG.exception("Admin ingest failed for district_id=%s", normalized)

    background_tasks.add_task(_ingest_job)

    return AdminIngestAccepted(
        district_id=normalized,
        recreate_collection=recreate,
    )


@router.post("/zip-db/import", response_model=AdminZipDbImportResult)
async def import_zip_ken_csv(
    settings: Annotated[Settings, Depends(get_settings)],
    ken_csv: Annotated[UploadFile, File(description="KEN_ALL_ROME.CSV (Japan Post / romaji)")],
    encoding: Annotated[str, Form(description="Кодировка файла: shift_jis или utf-8")] = "shift_jis",
) -> AdminZipDbImportResult:
    """
    Полная перезапись ``zip_codes.db`` из загруженного CSV (формат KEN_ALL_ROME).

    Файл из репозитория ``Index base/KEN_ALL_ROME.CSV`` подходит без изменений.
    """
    enc = encoding.strip().lower()
    if enc not in _ALLOWED_KEN_ENCODINGS:
        raise HTTPException(
            status_code=422,
            detail="Параметр encoding: допустимы только shift_jis или utf-8.",
        )

    name_lower = (ken_csv.filename or "").lower()
    if not name_lower.endswith(".csv"):
        raise HTTPException(status_code=415, detail="Ожидается файл с расширением .csv")

    suffix = Path(ken_csv.filename or "ken.csv").suffix or ".csv"
    tmp_csv: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_csv = Path(tmp.name)
            total = 0
            while True:
                chunk = await ken_csv.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_KEN_CSV_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"CSV слишком большой (лимит {_MAX_KEN_CSV_BYTES // (1024 * 1024)} МиБ).",
                    )
                tmp.write(chunk)

        db_path = settings.resolved_zip_db_path

        def _import() -> int:
            return load_csv_into_sqlite(tmp_csv, db_path, encoding=enc)

        try:
            rows = await asyncio.to_thread(_import)
        except sqlite3.Error as exc:
            LOG.exception("ZIP DB import SQLite failure")
            raise HTTPException(
                status_code=500,
                detail="Ошибка SQLite при импорте (проверьте свободное место и права на каталог data).",
            ) from exc

        sanity = await asyncio.to_thread(lookup_district_id, db_path, "1600022")

        try:
            rel = db_path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
        except ValueError:
            rel = str(db_path.resolve())

        LOG.info("Admin ZIP DB import: rows=%s db=%s encoding=%s", rows, rel, enc)
        return AdminZipDbImportResult(
            rows_imported=rows,
            sqlite_relative_path=rel,
            sanity_zip_1600022=sanity,
        )
    except UnicodeDecodeError as exc:
        LOG.warning("ZIP KEN CSV encoding error (%s): %s", enc, exc)
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось прочитать CSV как {enc}. Попробуйте другую кодировку.",
        ) from exc
    finally:
        if tmp_csv is not None:
            try:
                tmp_csv.unlink(missing_ok=True)
            except OSError as exc:
                LOG.warning("Temp CSV cleanup failed: %s", exc)


@router.post("/upload", response_model=AdminUploadResponse)
async def upload_district_pdf(
    pdf: Annotated[UploadFile, File(description="PDF с правилами утилизации")],
    lookup: Annotated[ZipLookupService, Depends(get_zip_lookup)],
    zip_code: Annotated[
        str,
        Form(description="Японский индекс 7 цифр; если указан — каталог и ingest по найденному district_id"),
    ] = "",
    district_id: Annotated[
        str,
        Form(description="district_id вручную, если индекс не указан"),
    ] = "",
) -> AdminUploadResponse:
    normalized = await resolve_zip_or_district(
        zip_code=zip_code,
        district_id=district_id,
        lookup=lookup,
    )

    mime = (pdf.content_type or "").split(";")[0].strip().lower()
    name_lower = (pdf.filename or "").lower()
    if mime not in ("application/pdf", "application/x-pdf") and not name_lower.endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Ожидается файл PDF.")

    raw = await pdf.read()
    if len(raw) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF слишком большой.")

    dest_dir = REPO_ROOT / "data" / "sources" / normalized
    dest_dir.mkdir(parents=True, exist_ok=True)
    fname = _safe_pdf_filename(pdf.filename or "rules.pdf")
    dest_path = dest_dir / fname
    dest_path.write_bytes(raw)

    rel = dest_path.relative_to(REPO_ROOT).as_posix()
    LOG.info("Admin upload saved PDF for district=%s -> %s", normalized, rel)

    return AdminUploadResponse(
        district_id=normalized,
        saved_relative_path=rel,
        filename=fname,
    )


@router.get("/tasks/ingest", response_model=AdminIngestAccepted, status_code=202)
async def schedule_ingest_query(
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    lookup: Annotated[ZipLookupService, Depends(get_zip_lookup)],
    recreate: bool = False,
    zip_code: Annotated[str, Query(description="Индекс 7 цифр (приоритет над district_id)")] = "",
    district_id: Annotated[str, Query(description="district_id, если индекс не указан")] = "",
) -> AdminIngestAccepted:
    """Тот же ingest, что по пути `/tasks/ingest/{district_id}`, но с опорой на индекс."""
    normalized = await resolve_zip_or_district(
        zip_code=zip_code,
        district_id=district_id,
        lookup=lookup,
    )
    return _enqueue_ingest(
        background_tasks,
        settings,
        normalized,
        recreate=recreate,
    )


@router.get("/tasks/ingest/{district_id}", response_model=AdminIngestAccepted, status_code=202)
async def schedule_ingest_path(
    district_id: str,
    background_tasks: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    recreate: bool = False,
) -> AdminIngestAccepted:
    """PDF → Markdown → Qdrant в фоне (PyMuPDF4LLM + логика ``init_vector_db``)."""
    normalized = normalize_strict_district_id(district_id)
    return _enqueue_ingest(
        background_tasks,
        settings,
        normalized,
        recreate=recreate,
    )


@router.get("/prompts/analyze", response_model=AnalyzePromptsPayload)
async def get_analyze_prompts() -> AnalyzePromptsPayload:
    """Текущие промпты Vision + вердикта (файл ``data/ai_prompts.json`` или дефолты)."""
    return load_analyze_prompts()


@router.put("/prompts/analyze", response_model=AnalyzePromptsPayload)
async def put_analyze_prompts(body: AnalyzePromptsPayload) -> AnalyzePromptsPayload:
    """Сохранить промпты; следующий ``POST /analyze`` подхватит без перезапуска."""
    save_analyze_prompts(body)
    return body
