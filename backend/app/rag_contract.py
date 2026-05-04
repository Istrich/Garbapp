"""
Единый контракт RAG между backend и скриптами ingestion.

Менять значения здесь и перегенерировать коллекцию Qdrant при смене модели или размерности.
"""

from __future__ import annotations

# Совпадает с OpenAI embeddings для chunks и запросов
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SIZE = 1536

DEFAULT_QDRANT_COLLECTION = "garbage_rules"

# Payload / фильтры Qdrant (ключи должны совпадать у ingest и analyze)
METADATA_DISTRICT_KEY = "district_id"
PAYLOAD_TEXT_KEY = "text"
# Дублируется в payload Qdrant для отладки и прозрачности (не участвует в фильтре RAG)
PAYLOAD_DISTRICT_LABEL_KEY = "district_label_ru"

# Значение по умолчанию для текущего набора Markdown Синдзюку
DEFAULT_INGEST_DISTRICT_ID = "shinjuku"

# Локальный Qdrant без Docker-сети
DEFAULT_LOCAL_QDRANT_URL = "http://127.0.0.1:6333"
