"""Location / postal code lookup schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LocationResponse(BaseModel):
    """Successful lookup of district by zip code."""

    zip_code: str = Field(
        ...,
        description="Нормализованный семизначный почтовый индекс без дефиса",
        examples=["1600022"],
    )
    district_id: str = Field(
        ...,
        description="Идентификатор муниципалитета для правил утилизации и RAG",
        examples=["shinjuku"],
    )
