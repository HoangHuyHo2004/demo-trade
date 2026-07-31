FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/services/api:/app/services/worker

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/worker/pyproject.toml services/worker/pyproject.toml

RUN pip install --upgrade pip && \
    pip install -e services/api[dev] && \
    pip install -e services/worker

COPY services/api services/api
COPY services/worker services/worker

WORKDIR /app/services/api

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
