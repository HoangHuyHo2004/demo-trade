"""Worker tasks.

Phase 2: refresh daily bars for every asset that appears on any
watchlist. The heavy work runs in the API service's DB via a thin
per-task session; the worker sits on the same Redis broker and shares
the API's SQLAlchemy models.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from worker.celery_app import app

log = logging.getLogger(__name__)


@app.task(name="worker.tasks.heartbeat")
def heartbeat() -> str:
    log.info("worker heartbeat")
    return "ok"


@app.task(name="worker.tasks.refresh_quotes")
def refresh_quotes() -> str:
    """Kept for backwards compatibility; delegates to refresh_bars."""
    return refresh_bars.run(interval="1d", lookback_days=60)


@app.task(name="worker.tasks.refresh_bars")
def refresh_bars(interval: str = "1d", lookback_days: int = 60) -> str:
    """Refresh bars for every asset referenced by any watchlist item.

    Runs each fetch through :class:`BarRepository`, so it upserts and
    audits automatically.
    """
    return asyncio.run(_refresh_bars_async(interval, lookback_days))


@app.task(name="worker.tasks.run_backtest_job", bind=True, max_retries=0)
def run_backtest_job(self, job_public_id: str) -> str:
    """Execute a backtest job (spec §14 async pattern).

    The API creates the ``jobs`` row and enqueues this task by public_id.
    The worker hydrates its own DB session, calls the inline runner
    (same code path as the sync test flow), and updates the row.
    """
    return asyncio.run(_run_backtest_job_async(job_public_id))


async def _run_backtest_job_async(job_public_id: str) -> str:
    from app.db import SessionLocal
    from app.services.jobs import (
        JobStatus,
        fail as job_fail,
        load_job,
        run_backtest_job_inline,
        update_status,
    )

    async with SessionLocal() as session:
        job = await load_job(session, job_public_id)
        if job is None:
            log.warning("run_backtest_job: unknown public_id %s", job_public_id)
            return "unknown"
        await update_status(session, job, status=JobStatus.CALCULATING,
                             progress=0.1, message="worker picked up")
        try:
            await run_backtest_job_inline(session, job)
        except Exception as e:  # noqa: BLE001
            await job_fail(session, job, message=f"{type(e).__name__}: {e}")
            log.exception("run_backtest_job failed for %s", job_public_id)
            return "failed"
    return "ok"


async def _refresh_bars_async(interval: str, lookback_days: int) -> str:
    # Late imports: the worker image installs both packages, but tests
    # for the API service should not require celery to be importable.
    from app.db import SessionLocal
    from app.models.asset import Asset
    from app.models.watchlist import WatchlistItem
    from app.providers.registry import get_registry
    from app.services.bar_repository import BarRepository

    reg = get_registry()
    end = datetime.now(UTC)
    start = end - timedelta(days=lookback_days)
    processed = 0
    errors = 0

    async with SessionLocal() as session:
        stmt = select(Asset).join(WatchlistItem, WatchlistItem.asset_id == Asset.id).distinct()
        assets = list((await session.execute(stmt)).scalars().all())
        for a in assets:
            try:
                repo = BarRepository(session)
                provider = reg.market_data_for(a.market)
                await repo.get_or_fetch(a, provider, interval=interval, start=start, end=end)
                processed += 1
            except Exception:  # noqa: BLE001
                errors += 1
                log.exception("refresh_bars failed for %s", a.canonical_id)

    msg = f"refresh_bars interval={interval} lookback={lookback_days}d processed={processed} errors={errors}"
    log.info(msg)
    return msg
