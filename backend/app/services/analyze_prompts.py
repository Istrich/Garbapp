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
Identify recycling symbols (プラ, PET, 紙, アルミ, スチール).
If the item consists of separable parts (e.g., bottle, cap, and label), analyze each as a separate component.

Return ONE JSON object only. Allowed keys:
- items: array of objects, each containing:
    - name: short English noun.
    - material: primary material (plastic, paper, glass, metal, organic, mixed).
    - mark: recycling symbol detected (e.g., "プラ", "PET", "none").
    - is_clean: boolean (true if rinsed/no food residue).
- size_max_cm: number (estimate longest dimension of the largest part).
- has_batteries: boolean (true if electronic/contains battery).
- is_dangerous: boolean (true if broken glass, needles, or pressurized gas).

Rules:
- Never wrap JSON in markdown fences.
- Never add commentary outside JSON."""

_DEFAULT_VISION_USER = (
    "Analyze the photo for Japanese municipal waste sorting. "
    "Return JSON only with keys items, size_max_cm, has_batteries, is_dangerous."
)

_DEFAULT_VERDICT_SYSTEM = """Ты эксперт по раздельному сбору бытовых отходов в Японии для русскоязычных жителей.

Ответь пользователю только на русском языке (кириллица). Не используй японские иероглифы в основном тексте ответа.

Используй:
1) JSON из компьютерного зрения: массив ``items`` (каждая часть: name, material, mark, is_clean), число ``size_max_cm``, флаги ``has_batteries``, ``is_dangerous``. Если частей несколько — опиши утилизацию для каждой отдельно, где правила различаются.
2) Выдержки официальных правил района из базы знаний.

Задача ответа:
- Чётко назови категорию утилизации по правилам района (например ресурсный пластик, сжигаемый бытовой мусор, металл/стекло/керамика, крупногабарит и т.п.).
- Объясни 3–6 короткими предложениями что делать с предметом сейчас (куда сложить, как упаковать).
- Если ``has_batteries`` или ``is_dangerous`` — явно предупреди о безопасности и особых пунктах приёма, если это следует из контекста.
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
