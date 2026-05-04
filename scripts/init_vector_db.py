#!/usr/bin/env python3
"""Load knowledge markdown into Qdrant collection ``garbage_rules`` with embeddings."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_BACKEND_ROOT = ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.district_labels import district_label_ru
from app.rag_contract import (
    DEFAULT_INGEST_DISTRICT_ID,
    DEFAULT_LOCAL_QDRANT_URL,
    DEFAULT_QDRANT_COLLECTION,
    EMBEDDING_MODEL,
    METADATA_DISTRICT_KEY,
    PAYLOAD_DISTRICT_LABEL_KEY,
    PAYLOAD_TEXT_KEY,
    VECTOR_SIZE,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOG = logging.getLogger(__name__)

COLLECTION_DEFAULT = DEFAULT_QDRANT_COLLECTION


def load_markdown(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Markdown not found: {path}")
    return path.read_text(encoding="utf-8")


def split_by_waste_categories(text: str) -> list[Document]:
    """Split markdown preserving hierarchy (categories + April 2024 subsection).

    Level-2 headers match waste streams (Burnable, Non-burnable, Plastic, Sodai).
    Level-3 keeps the April 2024 plastic rule block intact as its own chunk.
    """
    splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "doc_title"),
            ("##", "category"),
            ("###", "subsection"),
        ],
        strip_headers=False,
    )
    docs = splitter.split_text(text)
    # Drop empty fragments (noise from edge cases at document boundaries).
    return [d for d in docs if d.page_content.strip()]


def attach_district_metadata(documents: list[Document], district_id: str) -> list[dict[str, Any]]:
    """Normalize LangChain documents into dicts with Qdrant-ready payloads."""
    label = district_label_ru(district_id)
    prefix = (
        f"Правила раздельного сбора отходов. Район: {label}. "
        f"Идентификатор района (district_id): {district_id}.\n\n"
    )
    rows: list[dict[str, Any]] = []
    for doc in documents:
        meta = dict(doc.metadata)
        meta[METADATA_DISTRICT_KEY] = district_id
        meta[PAYLOAD_DISTRICT_LABEL_KEY] = label
        rows.append({"page_content": prefix + doc.page_content.strip(), "metadata": meta})
    return rows


def embed_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    # API returns embeddings in the same order as inputs.
    ordered = sorted(resp.data, key=lambda item: item.index)
    return [item.embedding for item in ordered]


def ensure_collection(client: QdrantClient, name: str, *, recreate: bool) -> None:
    exists = client.collection_exists(name)
    if exists and recreate:
        LOG.info("Deleting existing collection %r", name)
        client.delete_collection(collection_name=name)
        exists = False

    if not exists:
        LOG.info("Creating collection %r (dim=%s, cosine)", name, VECTOR_SIZE)
        client.create_collection(
            collection_name=name,
            vectors_config=qmodels.VectorParams(
                size=VECTOR_SIZE,
                distance=qmodels.Distance.COSINE,
            ),
        )


def upsert_chunks(
    qdrant: QdrantClient,
    openai_client: OpenAI,
    collection: str,
    rows: list[dict[str, Any]],
) -> None:
    texts = [r["page_content"] for r in rows]
    embeddings = embed_batch(openai_client, texts)

    points: list[qmodels.PointStruct] = []
    namespace = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    for row, vector in zip(rows, embeddings, strict=True):
        chunk_id = uuid.uuid5(namespace, row["page_content"] + repr(row["metadata"]))
        payload = {
            METADATA_DISTRICT_KEY: row["metadata"][METADATA_DISTRICT_KEY],
            PAYLOAD_TEXT_KEY: row["page_content"],
            **{
                k: v
                for k, v in row["metadata"].items()
                if k != METADATA_DISTRICT_KEY and v not in (None, "")
            },
        }
        points.append(
            qmodels.PointStruct(
                id=str(chunk_id),
                vector=vector,
                payload=payload,
            )
        )

    LOG.info("Upserting %s points into %r", len(points), collection)
    qdrant.upload_points(collection_name=collection, points=points)


def _resolve_qdrant_api_key(url: str, raw: str | None) -> str | None:
    """Согласовано с backend: по HTTP ключ не отправляем без GARBAGE_QDRANT_HTTP_API_KEY=1."""
    key = (raw or "").strip() or None
    if not key:
        return None
    if url.startswith("https://"):
        return key
    allow_http = os.getenv("GARBAGE_QDRANT_HTTP_API_KEY", "").strip().lower() in ("1", "true", "yes")
    if url.startswith("http://") and not allow_http:
        LOG.warning(
            "QDRANT_API_KEY не используется по HTTP без GARBAGE_QDRANT_HTTP_API_KEY=1 "
            "(при необходимости задайте переменную).",
        )
        return None
    return key


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--markdown",
        type=Path,
        default=ROOT / "knowledge" / "shinjuku_rules.md",
        help="Source markdown path",
    )
    p.add_argument(
        "--district-id",
        default=DEFAULT_INGEST_DISTRICT_ID,
        help="Metadata district_id for all chunks (must match API filters)",
    )
    p.add_argument(
        "--collection",
        default=COLLECTION_DEFAULT,
        help="Qdrant collection name",
    )
    p.add_argument(
        "--recreate",
        action="store_true",
        help="Drop collection if it exists before upload",
    )
    return p.parse_args()


def ingest_markdown_to_qdrant(
    *,
    markdown_path: Path,
    district_id: str,
    collection: str,
    recreate: bool,
) -> int:
    """Embed markdown chunks and upsert into Qdrant. Returns number of chunks."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    qdrant_url = os.getenv("QDRANT_URL", DEFAULT_LOCAL_QDRANT_URL).strip()
    if not qdrant_url:
        raise RuntimeError("QDRANT_URL is empty")

    md_path = markdown_path.expanduser().resolve()

    raw = load_markdown(md_path)
    documents = split_by_waste_categories(raw)
    rows = attach_district_metadata(documents, district_id)
    LOG.info("Prepared %s chunks from %s", len(rows), md_path.name)

    q_base = qdrant_url.rstrip("/")
    qdrant_key = _resolve_qdrant_api_key(q_base, os.getenv("QDRANT_API_KEY"))
    qdrant = QdrantClient(
        url=q_base,
        api_key=qdrant_key,
        timeout=60,
        check_compatibility=False,
    )
    openai_client = OpenAI(api_key=api_key)

    ensure_collection(qdrant, collection, recreate=recreate)
    upsert_chunks(qdrant, openai_client, collection, rows)

    LOG.info(
        "Done. Collection %r ready with %s=%r metadata.",
        collection,
        METADATA_DISTRICT_KEY,
        district_id,
    )
    return len(rows)


def main() -> int:
    args = parse_args()

    try:
        ingest_markdown_to_qdrant(
            markdown_path=args.markdown,
            district_id=args.district_id,
            collection=args.collection,
            recreate=args.recreate,
        )
    except RuntimeError as exc:
        LOG.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
