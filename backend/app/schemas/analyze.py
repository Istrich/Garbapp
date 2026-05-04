"""Schemas for vision + RAG analyze pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class VisionItem(BaseModel):
    """Один компонент / часть отхода (капсула Vision)."""

    name: str = Field(..., description="Короткое английское имя части")
    material: str = Field(..., description="Основной материал (plastic, metal, …)")
    mark: str = Field(
        ...,
        description='Маркировка переработки: "プラ", "PET", "none" и т.д.',
    )
    is_clean: bool = Field(
        ...,
        description="true если ополаскивали / без заметных остатков еды",
    )

    @field_validator("name", "material", "mark", mode="before")
    @classmethod
    def strip_strings(cls, value: Any) -> Any:
        if value is None:
            return value
        if not isinstance(value, str):
            return value
        return value.strip()

    @field_validator("name", "material", mode="after")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("mark", mode="after")
    @classmethod
    def mark_fallback(cls, value: str) -> str:
        return value if value else "none"


class VisionAnalysis(BaseModel):
    """Structured output from GPT-4o vision (Step 1) — несколько компонентов + флаги."""

    items: list[VisionItem] = Field(
        ...,
        min_length=1,
        description="Разбор по отдельным частям (бутылка, крышка, этикетка, …)",
    )
    size_max_cm: float | None = Field(
        default=None,
        description="Оценка самой длинной стороны самой крупной части, см",
    )
    has_batteries: bool = Field(
        ...,
        description="true если электроника / есть батарея",
    )
    is_dangerous: bool = Field(
        ...,
        description="true если опасно (битое стекло, иглы, баллон под давлением)",
    )

    @field_validator("size_max_cm", mode="before")
    @classmethod
    def coerce_size_max(cls, value: Any) -> float | None:
        if value is None or value == "":
            return None
        return float(value)


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
