"""Worker tasks. Phase 1 is intentionally minimal."""
from __future__ import annotations

import logging

from worker.celery_app import app

log = logging.getLogger(__name__)


@app.task(name="worker.tasks.heartbeat")
def heartbeat() -> str:
    log.info("worker heartbeat")
    return "ok"


@app.task(name="worker.tasks.refresh_quotes")
def refresh_quotes() -> str:
    """Phase 2 will refresh cached quotes from live providers.

    In Phase 1 we log a no-op so operators can see the schedule firing.
    """
    log.info("refresh_quotes: no-op in Phase 1 (mock provider is computed on-demand)")
    return "noop"
