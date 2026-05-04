#!/usr/bin/env python3
"""Build SQLite zip_code → district_id mapping from KEN_ALL_ROME.CSV."""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

# Repo root = parent of scripts/
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
for p in (BACKEND, ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from app.services.ken_csv_import import load_csv_into_sqlite

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOG = logging.getLogger(__name__)

DEFAULT_CSV = ROOT / "Index base" / "KEN_ALL_ROME.CSV"
DEFAULT_DB = ROOT / "data" / "zip_codes.db"


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
