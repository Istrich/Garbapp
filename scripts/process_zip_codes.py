#!/usr/bin/env python3
"""Build SQLite zip_code → district_id mapping from KEN_ALL_ROME.CSV."""

from __future__ import annotations

import argparse
import csv
import logging
import sqlite3
import sys
from pathlib import Path

# Repo root = parent of scripts/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from garbage_data.municipalities import municipality_romaji_to_district_id

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOG = logging.getLogger(__name__)

DEFAULT_CSV = ROOT / "Index base" / "KEN_ALL_ROME.CSV"
DEFAULT_DB = ROOT / "data" / "zip_codes.db"


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


def load_csv_into_sqlite(csv_path: Path, db_path: Path, encoding: str = "shift_jis") -> int:
    """Insert rows from CSV into SQLite. Returns number of rows processed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    inserted = 0
    with sqlite3.connect(db_path) as conn:
        ensure_schema(conn)
        conn.execute("DELETE FROM zip_mapping")

        with csv_path.open(encoding=encoding, newline="") as fh:
            reader = csv.reader(fh)
            batch: list[tuple[str, str]] = []
            for row in reader:
                if len(row) < 6:
                    LOG.warning("Skipping short row (%s columns)", len(row))
                    continue
                zip_code = row[0].strip().strip('"')
                municipality_romaji = row[5].strip().strip('"')
                district_id = municipality_romaji_to_district_id(municipality_romaji)
                if not zip_code or not district_id:
                    continue
                batch.append((zip_code, district_id))
                inserted += 1

            conn.executemany(
                "INSERT OR REPLACE INTO zip_mapping (zip_code, district_id) VALUES (?, ?)",
                batch,
            )
        conn.commit()

    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help=f"Path to KEN_ALL_ROME.CSV (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Output SQLite path (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--encoding",
        default="shift_jis",
        help="CSV text encoding (Japan Post romaji files use shift_jis)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    csv_path: Path = args.csv.expanduser().resolve()
    db_path: Path = args.db.expanduser().resolve()

    if not csv_path.is_file():
        LOG.error("CSV not found: %s", csv_path)
        return 1

    try:
        count = load_csv_into_sqlite(csv_path, db_path, encoding=args.encoding)
    except UnicodeDecodeError as exc:
        LOG.error("Encoding error reading CSV as %s: %s", args.encoding, exc)
        return 1

    LOG.info("Wrote %s rows to %s", count, db_path)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT district_id FROM zip_mapping WHERE zip_code = ?",
            ("1600022",),
        ).fetchone()
        LOG.info("Sanity check 1600022 -> %s", row[0] if row else None)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
