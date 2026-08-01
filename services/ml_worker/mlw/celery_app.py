"""Celery app for ML training/inference tasks."""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

broker = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

app = Celery("demo_trade_ml", broker=broker, backend=backend, include=["mlw.tasks"])
app.conf.update(
    task_track_started=True,
    task_time_limit=15 * 60,   # 15m hard cap on training
    task_soft_time_limit=12 * 60,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        # Generate the daily prediction row for every SHADOW/CHAMPION model
        # so the /api/v1/ml/predictions endpoint has something to show.
        "ml-generate-predictions-hourly": {
            "task": "mlw.tasks.generate_predictions",
            "schedule": crontab(minute=15),   # every hour at :15
        },
        # Evaluate outcomes for predictions whose horizon has expired.
        "ml-evaluate-outcomes-daily": {
            "task": "mlw.tasks.evaluate_outcomes",
            "schedule": crontab(hour=1, minute=0),
        },
    },
)
