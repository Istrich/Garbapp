"""Filesystem roots shared across the backend."""

from __future__ import annotations

from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = _BACKEND_DIR.parent
