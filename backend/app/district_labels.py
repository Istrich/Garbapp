"""Человекочитаемые подписи районов для чанков RAG и ответа API."""

from __future__ import annotations

_LABELS: dict[str, str] = {
    # Токио (частые пресеты админки)
    "shinjuku": "Токио, специальный район Синдзюку",
    "minato": "Токио, специальный район Минато",
    "chuo": "Токио, специальный район Тюо",
    "shibuya": "Токио, специальный район Сибуя",
    # Саппоро — совпадает с zip_mapping (sapporo_shi_*)
    "sapporo": "Саппоро (Хоккайдо), город",
    "sapporo_shi_chuo": "Саппоро (Хоккайдо), центральный район (Tyuo)",
    "sapporo_shi_kita": "Саппоро (Хоккайдо), район Кита",
    "sapporo_shi_higashi": "Саппоро (Хоккайдо), район Хигаси",
    "sapporo_shi_shiroishi": "Саппоро (Хоккайдо), район Сироиси",
    "sapporo_shi_toyohira": "Саппоро (Хоккайдо), район Тоёхира",
    "sapporo_shi_minami": "Саппоро (Хоккайдо), район Минами",
    "sapporo_shi_nishi": "Саппоро (Хоккайдо), район Ниси",
    "sapporo_shi_atsubetsu": "Саппоро (Хоккайдо), район Ацубэцу",
    "sapporo_shi_teine": "Саппоро (Хоккайдо), район Тэйнэ",
    "sapporo_shi_kiyota": "Саппоро (Хоккайдо), район Киёта",
    # Легаси/ручные id
    "060_0000": "Саппоро (Хоккайдо), условный район (060_0000)",
}


def district_label_ru(district_id: str) -> str:
    """Краткая подпись для префикса текста чанков и поля ``district_label_ru`` в API."""
    key = district_id.strip().lower()
    if key in _LABELS:
        return _LABELS[key]
    readable = key.replace("_", " ").strip()
    return f"Муниципальный район ({readable})"
