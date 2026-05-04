"""Two-stage analyze flow: Vision (GPT-4o) → Qdrant RAG → verdict LLM."""

from __future__ import annotations

import json
import logging
import base64
import time

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue
from openai import AsyncOpenAI

from app.config import Settings
from app.district_labels import district_label_ru
from app.rag_contract import METADATA_DISTRICT_KEY, PAYLOAD_TEXT_KEY
from app.schemas.analyze import AnalyzeResponse, VisionAnalysis
from app.services.analyze_prompts import load_analyze_prompts

LOG = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})


async def vision_analyze(
    client: AsyncOpenAI,
    *,
    image_b64: str,
    mime_type: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> VisionAnalysis:
    """Step 1 — GPT-4o multimodal JSON."""
    completion = await client.chat.completions.create(
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                ],
            },
        ],
    )
    raw = completion.choices[0].message.content
    if not raw:
        raise ValueError("Vision model returned empty content")
    payload = json.loads(raw)
    return VisionAnalysis.model_validate(payload)


async def embed_query(client: AsyncOpenAI, *, text: str, model: str) -> list[float]:
    """Embedding vector for semantic search."""
    response = await client.embeddings.create(model=model, input=[text])
    return list(response.data[0].embedding)


def build_retrieval_query(district_id: str, vision: VisionAnalysis) -> str:
    """Natural-language query aligned with indexed Markdown chunks."""
    size_part = (
        f"{vision.size_cm:.1f} cm"
        if vision.size_cm is not None
        else "unknown size_cm"
    )
    return (
        f"Municipal waste sorting rules for district_id={district_id}. "
        f"Item {vision.object}, material {vision.material}, "
        f"estimated longest dimension {size_part}, "
        f"clean={'yes' if vision.is_clean else 'no'}. "
        "Plastic resource bags, burnable trash, metal ceramic glass, bulky waste."
    )


async def search_rules(
    qdrant: AsyncQdrantClient,
    openai: AsyncOpenAI,
    *,
    settings: Settings,
    district_id: str,
    vision: VisionAnalysis,
) -> list[str]:
    """Step 2a — dense retrieval with mandatory district filter."""
    query_text = build_retrieval_query(district_id, vision)
    t0 = time.perf_counter()
    vector = await embed_query(openai, text=query_text, model=settings.embedding_model)
    t_embed = time.perf_counter()

    query_response = await qdrant.query_points(
        collection_name=settings.qdrant_collection,
        query=vector,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key=METADATA_DISTRICT_KEY,
                    match=MatchValue(value=district_id),
                ),
            ],
        ),
        limit=settings.rag_top_k,
        with_payload=True,
    )
    hits = query_response.points
    t_done = time.perf_counter()

    LOG.info(
        "RAG timing district=%s embed_ms=%.0f query_points_ms=%.0f total_ms=%.0f hits=%s",
        district_id,
        (t_embed - t0) * 1000,
        (t_done - t_embed) * 1000,
        (t_done - t0) * 1000,
        len(hits),
    )

    excerpts: list[str] = []
    for hit in hits:
        text = ""
        if hit.payload:
            text = str(hit.payload.get(PAYLOAD_TEXT_KEY) or "").strip()
        if text:
            excerpts.append(text[:1200])
    return excerpts


async def verdict_from_context(
    client: AsyncOpenAI,
    *,
    model: str,
    district_id: str,
    district_label_ru: str,
    vision: VisionAnalysis,
    rag_excerpts: list[str],
    system_prompt: str,
) -> str:
    """Step 2b — reasoning LLM producing Russian verdict."""
    rag_block = (
        "\n\n---\n\n".join(rag_excerpts)
        if rag_excerpts
        else "(В базе не найдено релевантных выдержек для этого района — опирайся на общую логику и предупреди пользователя.)"
    )
    user_payload = (
        f"district_id: {district_id}\n"
        f"Название района (справочно): {district_label_ru}\n\n"
        f"Vision JSON:\n{vision.model_dump_json(indent=2)}\n\n"
        f"Выдержки правил района:\n{rag_block}"
    )
    completion = await client.chat.completions.create(
        model=model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
    )
    content = completion.choices[0].message.content
    if not content:
        raise ValueError("Verdict model returned empty content")
    return content.strip()


async def run_analyze(
    *,
    openai: AsyncOpenAI,
    qdrant: AsyncQdrantClient,
    settings: Settings,
    image_bytes: bytes,
    mime_type: str,
    district_id: str,
) -> AnalyzeResponse:
    """Execute vision → Qdrant → verdict."""
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f"Unsupported image type: {mime_type}")

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")

    prompts = load_analyze_prompts()

    vision = await vision_analyze(
        openai,
        image_b64=b64,
        mime_type=mime_type,
        model=settings.openai_vision_model,
        system_prompt=prompts.vision_system_prompt,
        user_prompt=prompts.vision_user_prompt,
    )
    LOG.info(
        "Vision result district=%s object=%s material=%s",
        district_id,
        vision.object,
        vision.material,
    )

    rag_excerpts = await search_rules(qdrant, openai, settings=settings, district_id=district_id, vision=vision)

    label_ru = district_label_ru(district_id)

    verdict = await verdict_from_context(
        openai,
        model=settings.openai_verdict_model,
        district_id=district_id,
        district_label_ru=label_ru,
        vision=vision,
        rag_excerpts=rag_excerpts,
        system_prompt=prompts.verdict_system_prompt,
    )

    preview = [excerpt[:320] + ("…" if len(excerpt) > 320 else "") for excerpt in rag_excerpts]

    return AnalyzeResponse(
        district_id=district_id,
        district_label_ru=label_ru,
        vision=vision,
        verdict_ru=verdict,
        rag_excerpts=preview,
    )
