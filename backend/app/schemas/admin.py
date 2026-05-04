"""Admin API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdminUploadResponse(BaseModel):
    district_id: str
    saved_relative_path: str = Field(description="Путь относительно корня репозитория")
    filename: str


class AdminIngestAccepted(BaseModel):
    status: str = Field(default="accepted", description="Задача поставлена в очередь FastAPI BackgroundTasks")
    district_id: str
    recreate_collection: bool


class AdminZipDbImportResult(BaseModel):
    """Результат импорта KEN_ALL_ROME (или совместимого CSV) в ``zip_codes.db``."""

    rows_imported: int = Field(description="Число вставленных строк (после фильтрации пустых)")
    sqlite_relative_path: str = Field(description="Путь к SQLite относительно корня репозитория, если внутри него")
    sanity_zip_1600022: str | None = Field(
        default=None,
        description="district_id для индекса 1600022 после импорта (если строка есть в CSV)",
    )
