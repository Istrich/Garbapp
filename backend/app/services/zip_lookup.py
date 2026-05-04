"""SQLite-backed postal code → district_id resolution."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path

LOG = logging.getLogger(__name__)


def normalize_japanese_zip(raw: str) -> str:
    """Keep digits only (accepts inputs like ``160-0022``)."""
    return "".join(ch for ch in raw if ch.isdigit())


class ZipLookupService:
    """Read-only access to ``zip_mapping`` table."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _fetch_sync(self, zip_digits: str) -> str | None:
        if not self._db_path.is_file():
            LOG.error("SQLite database missing at %s", self._db_path)
            raise FileNotFoundError(str(self._db_path))

        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT district_id FROM zip_mapping WHERE zip_code = ?",
                (zip_digits,),
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    async def get_district_id(self, normalized_zip: str) -> str | None:
        """Return ``district_id`` or ``None`` if zip is unknown."""
        return await asyncio.to_thread(self._fetch_sync, normalized_zip)
