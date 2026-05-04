"""Load/save editable prompts for Vision + verdict LLM calls (analyze pipeline)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.paths import REPO_ROOT
from app.schemas.prompts import AnalyzePromptsPayload

LOG = logging.getLogger(__name__)

_PROMPTS_FILE = REPO_ROOT / "data" / "ai_prompts.json"

_DEFAULT_VISION_SYSTEM = """You analyze photographs of everyday waste items for sorting guidance in Japan.
Return ONE JSON object only. Allowed keys (exact names):
- object: short English noun for the item (e.g. bucket, toothbrush).
- material: primary material in English (e.g. plastic, metal, mixed).
- size_cm: number — estimate the longest visible dimension in centimeters (decimals ok); use null only if impossible.
- is_clean: boolean — true if it looks rinsed / without heavy dirt or food residue.

Rules:
- Never wrap JSON in markdown fences.
- Never add commentary outside JSON."""

_DEFAULT_VISION_USER = (
    "Identify the waste item for municipal sorting. "
    "Return JSON only with keys object, material, size_cm, is_clean."
)

_DEFAULT_VERDICT_SYSTEM = """Ты эксперт по раздельному сбору бытовых отходов в Японии для русскоязычных жителей.

Ответь пользователю только на русском языке (кириллица). Не используй японские иероглифы в основном тексте ответа.

Используй:
1) JSON из компьютерного зрения (объект, материал, размер, чистота).
2) Выдержки официальных правил района из базы знаний.

Задача ответа:
- Чётко назови категорию утилизации по правилам района (например ресурсный пластик, сжигаемый бытовой мусор, металл/стекло/керамика, крупногабарит и т.п.).
- Объясни 3–6 короткими предложениями что делать с предметом сейчас (куда сложить, как упаковать).
- Если для района действует правило апреля 2024 про однородный пластик примерно до 30 см и толщину около 5 мм — явно учитывай его для подходящих предметов.
- Если данных не хватает — напиши что именно нужно уточнить или сфотографировать."""


def default_analyze_prompts() -> AnalyzePromptsPayload:
    """Значения по умолчанию (как в коде до редактирования через UI)."""
    return AnalyzePromptsPayload(
        vision_system_prompt=_DEFAULT_VISION_SYSTEM,
        vision_user_prompt=_DEFAULT_VISION_USER,
        verdict_system_prompt=_DEFAULT_VERDICT_SYSTEM,
    )


def load_analyze_prompts() -> AnalyzePromptsPayload:
    """Читает ``data/ai_prompts.json``; при отсутствии или ошибке — дефолты."""
    base = default_analyze_prompts()
    path = _PROMPTS_FILE
    if not path.is_file():
        return base
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Корень JSON должен быть объектом.")
        merged = {
            "vision_system_prompt": raw.get("vision_system_prompt") or base.vision_system_prompt,
            "vision_user_prompt": raw.get("vision_user_prompt") or base.vision_user_prompt,
            "verdict_system_prompt": raw.get("verdict_system_prompt") or base.verdict_system_prompt,
        }
        return AnalyzePromptsPayload.model_validate(merged)
    except Exception as exc:
        LOG.warning("Не удалось прочитать %s, используются дефолты: %s", path, exc)
        return base


def save_analyze_prompts(payload: AnalyzePromptsPayload) -> None:
    """Атомарная запись JSON в ``data/ai_prompts.json``."""
    path = _PROMPTS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    data = payload.model_dump()
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = Path(str(path) + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        if tmp.is_file():
            tmp.unlink(missing_ok=True)
        raise
    LOG.info("Сохранены промпты analyze: %s", path.relative_to(REPO_ROOT).as_posix())
