#!/usr/bin/env python3
"""Интеграционная проверка цепочки Garbage App.

Сценарий QA (описание для человека): пользователь с индексом **1600022** (Синдзюку),
фото условного **пластикового ведра ~25 см**. Скрипт не подставляет текст вместо Vision —
он генерирует простое синтетическое изображение «ведро», чтобы GPT-4o мог классифицировать
объект как пластиковую тару примерно бытового размера.

Требования к окружению
---------------------
- Запущенный backend (например ``uvicorn app.main:app`` из каталога ``backend/``).
- В переменных окружения сервера заданы ``OPENAI_API_KEY``, ``QDRANT_URL`` (и при необходимости ключ Qdrant).
- Коллекция Qdrant ``garbage_rules`` заполнена (``scripts/init_vector_db.py``).
- SQLite ``data/zip_codes.db`` создана (``scripts/process_zip_codes.py``).

Зависимости клиента::

    pip install -r scripts/integration/requirements.txt

Запуск::

    python scripts/integration/test_full_chain.py --base-url http://127.0.0.1:8000

Опционально свой кадр::

    python scripts/integration/test_full_chain.py --image path/to/bucket.jpg

Строгие проверки смысла (могут быть чувствительны к ответу модели)::

    python scripts/integration/test_full_chain.py --strict
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_synthetic_bucket_jpeg() -> bytes:
    """Небольшое JPEG «ведро»: тёмное тело + овал горловины на светлом фоне."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:  # pragma: no cover - runtime hint
        raise SystemExit(
            "Установите зависимости: pip install -r scripts/integration/requirements.txt",
        ) from exc

    size = (640, 640)
    img = Image.new("RGB", size, (238, 239, 242))
    draw = ImageDraw.Draw(img)

    body = [(180, 220), (460, 520)]
    draw.rounded_rectangle(body, radius=36, fill=(32, 34, 40))

    rim_bbox = (170, 170), (470, 260)
    draw.ellipse([*rim_bbox[0], *rim_bbox[1]], outline=(55, 58, 65), width=14)
    draw.ellipse([185, 185, 455, 245], fill=(48, 50, 56))

    handle_bbox = (430, 240), (520, 360)
    draw.arc([*handle_bbox[0], *handle_bbox[1]], start=200, end=340, fill=(28, 30, 36), width=16)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _call_location(client: Any, base_url: str, zip_code: str) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/v1/location/{zip_code}"
    resp = client.get(url)
    try:
        resp.raise_for_status()
    except Exception as exc:  # pragma: no cover - diagnostic path
        detail = getattr(resp, "text", "")[:800]
        raise RuntimeError(f"GET {url} failed: {exc}\n{detail}") from exc
    return resp.json()


def _call_analyze(
    client: Any,
    base_url: str,
    *,
    district_id: str,
    image_bytes: bytes,
    filename: str,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/v1/analyze"
    files = {"image": (filename, image_bytes, "image/jpeg")}
    data = {"district_id": district_id}
    resp = client.post(url, files=files, data=data)
    try:
        resp.raise_for_status()
    except Exception as exc:  # pragma: no cover - diagnostic path
        detail = getattr(resp, "text", "")[:1200]
        raise RuntimeError(f"POST {url} failed: {exc}\n{detail}") from exc
    return resp.json()


def _assert_semantics(body: dict[str, Any], *, strict: bool) -> list[str]:
    """Мягкие эвристики; при ``strict`` превращаются в ошибки."""
    warnings: list[str] = []
    vision = body.get("vision") or {}
    items = vision.get("items") if isinstance(vision.get("items"), list) else []
    names_mats = " ".join(
        f"{str(it.get('name', '')).lower()} {str(it.get('material', '')).lower()}"
        for it in items
        if isinstance(it, dict)
    )
    verdict = str(body.get("verdict_ru", "")).lower()
    size_max = vision.get("size_max_cm")

    if strict:
        plastic_hit = "plastic" in names_mats or "пластик" in verdict
        bucket_hit = any(
            k in names_mats for k in ("bucket", "pail", "bin", "container")
        )
        verdict_hit = any(
            token in verdict
            for token in ("ресурс", "пластик", "утилиз")
        )
        if not bucket_hit:
            warnings.append(f"[strict] Vision items не похожи на ведро: {names_mats!r}.")
        if not plastic_hit:
            warnings.append("[strict] Не найден явный признак пластика в items/вердикте.")
        if isinstance(size_max, (int, float)) and not (15 <= float(size_max) <= 45):
            warnings.append(f"[strict] size_max_cm={size_max} вне диапазона 15–45 см.")
        if not verdict_hit:
            warnings.append("[strict] Вердикт не содержит ожидаемых ключевых слов.")

    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Интеграционный тест цепочки индекс → analyze.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Базовый URL FastAPI (без завершающего слэша)",
    )
    parser.add_argument(
        "--zip-code",
        default="1600022",
        help="Почтовый индекс для шага локации",
    )
    parser.add_argument(
        "--district-id",
        default="shinjuku",
        help="district_id для шага analyze (должен совпадать с правилами в Qdrant)",
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=None,
        help="Файл JPEG/PNG/WebP; если не задан — генерируется синтетическое «ведро»",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Дополнительные проверки смысла (зависят от ответа GPT)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Таймаут HTTP-клиента, сек.",
    )
    args = parser.parse_args()

    try:
        import httpx
    except ImportError as exc:
        raise SystemExit(
            "Нужен httpx: pip install -r scripts/integration/requirements.txt",
        ) from exc

    root = _repo_root()
    print(f"[integration] repo root: {root}")

    # --- Шаг A: локация по индексу ---
    with httpx.Client(timeout=args.timeout) as client:
        loc = _call_location(client, args.base_url, args.zip_code)

    print("[integration] location response:")
    print(json.dumps(loc, ensure_ascii=False, indent=2))

    if loc.get("zip_code") != args.zip_code.replace("-", "").strip():
        print("[FAIL] zip_code в ответе не совпадает с ожидаемым после нормализации.", file=sys.stderr)
        return 1

    district = loc.get("district_id")
    if district != args.district_id:
        print(
            f"[FAIL] Ожидался district_id={args.district_id!r}, получено {district!r}.",
            file=sys.stderr,
        )
        return 1

    # --- Шаг B: изображение ---
    if args.image:
        img_path = args.image.expanduser().resolve()
        if not img_path.is_file():
            print(f"[FAIL] Файл изображения не найден: {img_path}", file=sys.stderr)
            return 1
        raw = img_path.read_bytes()
        fname = img_path.name
        mime_hint = fname.lower()
    else:
        raw = _build_synthetic_bucket_jpeg()
        fname = "synthetic_bucket.jpg"

    # --- Шаг C: analyze ---
    with httpx.Client(timeout=args.timeout) as client:
        body = _call_analyze(
            client,
            args.base_url,
            district_id=args.district_id,
            image_bytes=raw,
            filename=fname,
        )

    print("[integration] analyze response (укороченный rag_excerpts):")
    preview = dict(body)
    if isinstance(preview.get("rag_excerpts"), list):
        preview["rag_excerpts"] = preview["rag_excerpts"][:2]
    print(json.dumps(preview, ensure_ascii=False, indent=2))

    verdict = body.get("verdict_ru")
    if not verdict or len(str(verdict).strip()) < 40:
        print("[FAIL] Пустой или слишком короткий verdict_ru.", file=sys.stderr)
        return 1

    semantics = _assert_semantics(body, strict=args.strict)
    if semantics:
        for line in semantics:
            print(line, file=sys.stderr)
        if args.strict:
            print("[FAIL] Строгие проверки смысла не пройдены.", file=sys.stderr)
            return 1

    print("[integration] OK — цепочка индекс → Vision → Qdrant → вердикт отработала.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
