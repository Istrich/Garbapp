# Multi-stage-friendly image: build from repository root (--file backend/Dockerfile)
FROM python:3.11-slim-bookworm

WORKDIR /workspace
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace/backend

RUN pip install --no-cache-dir --upgrade pip

COPY backend/requirements-backend.txt /workspace/backend/requirements-backend.txt
RUN pip install --no-cache-dir -r /workspace/backend/requirements-backend.txt

COPY backend /workspace/backend
COPY garbage_data /workspace/garbage_data
COPY scripts /workspace/scripts
COPY knowledge /workspace/knowledge
COPY telegram-miniapp /workspace/telegram-miniapp
COPY data /workspace/data-incoming

# zip_codes.db: use repo data/zip_codes.db in build context if present (full Japan mapping),
# otherwise build a small seed DB from garbage_data/seeds/ken_all_sample.csv (Railway/CI).
RUN mkdir -p /workspace/data/sources /workspace/knowledge/generated && \
    if [ -f /workspace/data-incoming/zip_codes.db ] && [ -s /workspace/data-incoming/zip_codes.db ]; then \
      cp /workspace/data-incoming/zip_codes.db /workspace/data/zip_codes.db; \
      echo "zip_codes.db: copied from build context data/zip_codes.db"; \
    else \
      python /workspace/scripts/process_zip_codes.py \
        --csv /workspace/garbage_data/seeds/ken_all_sample.csv \
        --encoding utf-8 \
        --db /workspace/data/zip_codes.db && \
      echo "zip_codes.db: built from seed CSV (for full coverage, add data/zip_codes.db to build context)"; \
    fi && \
    rm -rf /workspace/data-incoming

WORKDIR /workspace/backend
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
