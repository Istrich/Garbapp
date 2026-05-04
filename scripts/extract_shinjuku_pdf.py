#!/usr/bin/env python3
"""Download Shinjuku flyer PDF (optional) and extract Markdown via PyMuPDF4LLM."""

from __future__ import annotations

import argparse
import logging
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from garbage_data.pdf_extract import pdf_to_markdown

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOG = logging.getLogger(__name__)

DEFAULT_URL = "https://www.city.shinjuku.lg.jp/content/000378895.pdf"
DEFAULT_OUT_MD = ROOT / "knowledge" / "generated" / "000378895_extract.md"


def download_pdf(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    LOG.info("Downloading %s -> %s", url, dest)
    urllib.request.urlretrieve(url, dest)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Local PDF path (if omitted and --fetch is set, downloads to --pdf-cache)",
    )
    p.add_argument(
        "--pdf-cache",
        type=Path,
        default=ROOT / "data" / "sources" / "000378895.pdf",
        help="Where to store downloaded PDF when using --fetch",
    )
    p.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="Official Shinjuku flyer URL",
    )
    p.add_argument(
        "--fetch",
        action="store_true",
        help="Download PDF from --url before extraction",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUT_MD,
        help="Markdown output path",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    pdf_path = args.pdf
    if args.fetch or pdf_path is None:
        pdf_path = args.pdf_cache.expanduser().resolve()
        if args.fetch or not pdf_path.is_file():
            download_pdf(args.url, pdf_path)
    else:
        pdf_path = pdf_path.expanduser().resolve()

    if not pdf_path.is_file():
        LOG.error("PDF not found: %s", pdf_path)
        return 1

    try:
        md = pdf_to_markdown(pdf_path)
    except ImportError:
        LOG.exception("Missing pymupdf4llm — pip install -r requirements-data.txt")
        return 1

    out = args.output.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "<!-- Auto-generated from official PDF; review before RAG ingestion. -->\n\n"
    )
    out.write_text(header + md, encoding="utf-8")
    LOG.info("Wrote %s (%s chars)", out, len(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
