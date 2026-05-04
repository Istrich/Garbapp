"""Extract Markdown-oriented text from municipality PDFs using PyMuPDF4LLM."""

from __future__ import annotations

from pathlib import Path


def pdf_to_markdown(pdf_path: Path) -> str:
    """Convert a PDF file to Markdown-like text suitable for RAG chunking.

    Args:
        pdf_path: Existing PDF on disk.

    Returns:
        Markdown string produced by pymupdf4llm.

    Raises:
        FileNotFoundError: If ``pdf_path`` does not exist.
        ImportError: If pymupdf4llm is not installed.
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(str(pdf_path))

    try:
        import pymupdf4llm
    except ImportError as exc:  # pragma: no cover - env-specific
        raise ImportError(
            "Install optional dependency pymupdf4llm (see requirements-data.txt)."
        ) from exc

    return pymupdf4llm.to_markdown(str(pdf_path))
