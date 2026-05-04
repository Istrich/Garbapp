"""Schemas for vision + RAG analyze pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field, field_validator


class VisionAnalysis(BaseModel):
    """Structured output from GPT-4o vision (Step 1)."""

    object: str = Field(..., description="Detected item name (English noun)")
    material: str = Field(..., description="Primary material (English)")
    size_cm: float | None = Field(
        default=None,
        description="Estimated longest dimension in centimeters",
    )
    is_clean: bool = Field(
        ...,
        validation_alias=AliasChoices("is_clean", "clean"),
        description="Whether the item appears rinsed / low residue",
    )

    @field_validator("size_cm", mode="before")
    @classmethod
    def coerce_size(cls, value: Any) -> float | None:
        if value is None or value == "":
            return None
        return float(value)

    @field_validator("object", "material", mode="before")
    @classmethod
    def nonempty_strip(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("expected string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class AnalyzeResponse(BaseModel):
    """API response after vision + RAG + verdict (Steps 1–2)."""

    district_id: str = Field(..., description="Район для фильтрации правил")
    district_label_ru: str = Field(
        ...,
        description="Человекочитаемое название района (по district_id)",
    )
    vision: VisionAnalysis = Field(..., description="Результат шага Vision")
    verdict_ru: str = Field(..., description="Итоговая рекомендация на русском")
    rag_excerpts: list[str] = Field(
        default_factory=list,
        description="Короткие выдержки из найденных правил (для прозрачности UX)",
    )
