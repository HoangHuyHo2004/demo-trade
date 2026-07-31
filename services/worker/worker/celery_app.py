"""Celery application + beat schedule.

Phase 1: only a heartbeat + a stubbed quote-refresh job that logs. Real
provider ingestion is wired in Phase 2 once concrete adapters exist.
"""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

broker = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

app = Celery("demo_trade", broker=broker, backend=backend, include=["worker.tasks"])
app.conf.update(
    task_track_started=True,
    task_time_limit=60,
    task_soft_time_limit=45,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "heartbeat-every-minute": {
            "task": "worker.tasks.heartbeat",
            "schedule": 60.0,
        },
        "refresh-quotes-every-15m": {
            "task": "worker.tasks.refresh_quotes",
            "schedule": crontab(minute="*/15"),
        },
    },
)
