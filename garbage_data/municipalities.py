"""Normalize municipality names from Japan Post KEN_ALL_ROME romaji fields."""

from __future__ import annotations


def municipality_romaji_to_district_id(romaji: str) -> str:
    """Map CSV romaji municipality (column index 5) to `district_id`.

    Rules:
        - Trim and collapse internal whitespace.
        - Split tokens; if the last token is ``KU`` (ward), drop it — mirrors
          examples such as ``SHINJUKU KU`` → ``shinjuku``.
        - Join remaining tokens with underscores and lowercase.

    Args:
        romaji: Municipality field from ``KEN_ALL_ROME.CSV`` (ASCII romaji).

    Returns:
        Snake-case identifier suitable for metadata filtering (e.g. Qdrant).
    """
    parts = romaji.strip().upper().split()
    if not parts:
        return ""

    if len(parts) >= 2 and parts[-1] == "KU":
        parts = parts[:-1]

    return "_".join(parts).lower()
