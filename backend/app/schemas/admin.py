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
