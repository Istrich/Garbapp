"""Schemas for editable analyze (Vision + verdict) prompts."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AnalyzePromptsPayload(BaseModel):
    """Промпты для POST /api/v1/analyze (vision + финальный ответ)."""

    vision_system_prompt: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        description="Системный промпт модели распознавания изображения (JSON).",
    )
    vision_user_prompt: str = Field(
        ...,
        min_length=1,
        max_length=50_000,
        description="Текст пользователя к изображению (краткая инструкция).",
    )
    verdict_system_prompt: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        description="Системный промпт для итогового ответа по правилам района (русский).",
    )

    @field_validator("vision_system_prompt", "vision_user_prompt", "verdict_system_prompt")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Промпт не может быть пустым.")
        return stripped
