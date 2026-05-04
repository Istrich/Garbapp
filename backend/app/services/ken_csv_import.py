"""Импорт Japan Post KEN_ALL_ROME.CSV → SQLite ``zip_mapping`` (почтовый индекс → district_id)."""

from __future__ import annotations

import csv
import gc
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

from app.paths import REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from garbage_data.municipalities import municipality_romaji_to_district_id

LOG = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50_000


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS zip_mapping (
            zip_code TEXT NOT NULL PRIMARY KEY,
            district_id TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_zip_mapping_zip ON zip_mapping (zip_code)"
    )


def load_csv_into_sqlite(
    csv_path: Path,
    db_path: Path,
    encoding: str = "shift_jis",
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    """
    Полная перезапись таблицы ``zip_mapping`` из CSV.

    Пишет во временный файл в каталоге ``db_path``, затем атомарно заменяет
    готовую базу, чтобы не оставлять повреждённый ``zip_codes.db`` при ошибке.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="zip_codes_", suffix=".db")
    os.close(fd)
    tmp_db = Path(tmp_name)

    inserted = 0
    skipped_short = 0
    try:
        with sqlite3.connect(tmp_db) as conn:
            ensure_schema(conn)
            conn.execute("DELETE FROM zip_mapping")
            with csv_path.open(encoding=encoding, newline="") as fh:
                reader = csv.reader(fh)
                batch: list[tuple[str, str]] = []
                for row in reader:
                    if len(row) < 6:
                        skipped_short += 1
                        continue
                    zip_code = row[0].strip().strip('"')
                    municipality_romaji = row[5].strip().strip('"')
                    district_id = municipality_romaji_to_district_id(municipality_romaji)
                    if not zip_code or not district_id:
                        continue
                    batch.append((zip_code, district_id))
                    inserted += 1
                    if len(batch) >= batch_size:
                        conn.executemany(
                            "INSERT OR REPLACE INTO zip_mapping (zip_code, district_id) VALUES (?, ?)",
                            batch,
                        )
                        conn.commit()
                        batch.clear()
                if batch:
                    conn.executemany(
                        "INSERT OR REPLACE INTO zip_mapping (zip_code, district_id) VALUES (?, ?)",
                        batch,
                    )
                conn.commit()
        shutil.copyfile(tmp_db, db_path)
    except Exception:
        raise
    finally:
        gc.collect()
        time.sleep(0.05)
        try:
            tmp_db.unlink(missing_ok=True)
        except OSError as exc:
            LOG.warning("Could not remove temp db %s: %s", tmp_db, exc)

    if skipped_short:
        LOG.info("ZIP KEN import: skipped %s short CSV rows", skipped_short)
    LOG.info("ZIP KEN import: wrote %s rows to %s", inserted, db_path)
    return inserted


def lookup_district_id(db_path: Path, zip_code: str) -> str | None:
    """Одна выборка для sanity-check после импорта."""
    if not db_path.is_file():
        return None
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT district_id FROM zip_mapping WHERE zip_code = ?",
            (zip_code,),
        ).fetchone()
        return row[0] if row else None
