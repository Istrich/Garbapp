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

RUN mkdir -p /workspace/data/sources /workspace/knowledge/generated

WORKDIR /workspace/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
