"""Admin-triggered PDF → Markdown → Qdrant ingestion (async wrappers)."""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
from pathlib import Path

from app.paths import REPO_ROOT

LOG = logging.getLogger(__name__)


def _ensure_import_paths() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    backend = REPO_ROOT / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))


def _load_init_vector_db_module():
    """Load ``scripts/init_vector_db.py`` as a module (CLI lives alongside)."""
    _ensure_import_paths()
    path = REPO_ROOT / "scripts" / "init_vector_db.py"
    spec = importlib.util.spec_from_file_location("init_vector_db_dynamic", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_latest_pdf(sources_dir: Path) -> Path | None:
    """Pick the most recently modified ``*.pdf`` under ``sources_dir``."""
    pdfs = sorted(sources_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    return pdfs[0] if pdfs else None


async def pdf_bytes_to_markdown_file(pdf_path: Path, output_md: Path) -> None:
    """PyMuPDF4LLM extraction (blocking → thread)."""

    def _run() -> None:
        _ensure_import_paths()
        from garbage_data.pdf_extract import pdf_to_markdown

        md = pdf_to_markdown(pdf_path)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        header = "<!-- Auto-generated from PDF (admin ingest). -->\n\n"
        output_md.write_text(header + md, encoding="utf-8")
        LOG.info("Wrote markdown extract %s (%s chars)", output_md, len(md))

    await asyncio.to_thread(_run)


async def run_markdown_ingest(
    *,
    markdown_path: Path,
    district_id: str,
    collection: str,
    recreate_collection: bool,
) -> int:
    """Invoke shared ingestion logic (embeddings + Qdrant upsert). Returns chunk count."""

    def _run() -> int:
        mod = _load_init_vector_db_module()
        fn = getattr(mod, "ingest_markdown_to_qdrant", None)
        if fn is None:
            raise RuntimeError("init_vector_db.ingest_markdown_to_qdrant missing")
        return fn(
            markdown_path=markdown_path,
            district_id=district_id,
            collection=collection,
            recreate=recreate_collection,
        )

    return await asyncio.to_thread(_run)


async def run_full_ingest_pipeline(
    *,
    district_id: str,
    collection: str,
    recreate_collection: bool,
) -> dict[str, str | int]:
    """PDF in ``data/sources/{district_id}/`` → extract MD → Qdrant."""
    sources = REPO_ROOT / "data" / "sources" / district_id
    pdf_path = find_latest_pdf(sources)
    if pdf_path is None:
        raise FileNotFoundError(f"No PDF found under {sources}")

    md_path = REPO_ROOT / "knowledge" / "generated" / f"{district_id}_extract.md"
    await pdf_bytes_to_markdown_file(pdf_path, md_path)

    chunks = await run_markdown_ingest(
        markdown_path=md_path,
        district_id=district_id,
        collection=collection,
        recreate_collection=recreate_collection,
    )

    return {
        "district_id": district_id,
        "pdf_used": pdf_path.name,
        "markdown_written": str(md_path.relative_to(REPO_ROOT)),
        "chunks_upserted": chunks,
        "collection": collection,
    }
