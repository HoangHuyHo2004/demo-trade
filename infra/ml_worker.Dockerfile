FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/services/api:/app/services/ml_worker

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# api's pyproject brings the shared deps (SQLAlchemy, models, etc.); we
# install the api package too so `from app.models.ml import ...` works
# via PYTHONPATH.
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/ml_worker/pyproject.toml services/ml_worker/pyproject.toml
RUN pip install --upgrade pip && \
    pip install -e services/api && \
    pip install -e services/ml_worker

COPY services/api services/api
COPY services/ml_worker services/ml_worker

# Persistent volume for saved model artifacts
RUN mkdir -p /var/lib/demo-trade/ml

WORKDIR /app/services/ml_worker

CMD ["celery", "-A", "mlw.celery_app:app", "worker", "-B", "--loglevel=INFO"]
