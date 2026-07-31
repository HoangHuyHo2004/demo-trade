"""Async-job pattern (spec §14).

Two execution paths for the same job:

- **Sync** (tests + demo without Redis): call ``run_job_now`` on the
  API session inline. The job row transitions QUEUED → CALCULATING →
  COMPLETE within the request. Result JSON is stored on the row.
- **Async** (production): API creates the job row and enqueues a
  Celery task by public_id. The worker picks it up, hydrates its own
  DB session, and updates the same row.

Both paths write to the same ``jobs`` table so ``GET /api/v1/jobs/{id}``
returns identical shape either way.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.job import Job, JobKind, JobStatus

log = get_logger(__name__)


async def create_job(
    session: AsyncSession, *, kind: str, user_id: int | None, payload: dict,
) -> Job:
    job = Job(
        public_id=f"{kind}_{uuid.uuid4().hex[:16]}",
        user_id=user_id,
        kind=kind,
        status=JobStatus.QUEUED.value,
        payload_json=json.dumps(payload, default=str),
        created_at=datetime.now(UTC),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def load_job(session: AsyncSession, public_id: str) -> Job | None:
    return (await session.execute(
        select(Job).where(Job.public_id == public_id)
    )).scalar_one_or_none()


async def update_status(
    session: AsyncSession, job: Job, *,
    status: JobStatus, progress: float | None = None, message: str = "",
) -> None:
    job.status = status.value
    if progress is not None:
        job.progress = Decimal(f"{max(0.0, min(1.0, progress)):.3f}")
    if message:
        job.message = message[:500]
    if status is JobStatus.CALCULATING and job.started_at is None:
        job.started_at = datetime.now(UTC)
    if status in (JobStatus.COMPLETE, JobStatus.FAILED):
        job.finished_at = datetime.now(UTC)
    await session.commit()


async def complete(
    session: AsyncSession, job: Job, *, result: dict,
) -> None:
    job.result_json = json.dumps(result, default=str)
    await update_status(session, job, status=JobStatus.COMPLETE,
                         progress=1.0, message="ok")


async def fail(session: AsyncSession, job: Job, *, message: str) -> None:
    await update_status(session, job, status=JobStatus.FAILED, message=message)


def job_to_dict(job: Job) -> dict[str, Any]:
    return {
        "job_id": job.public_id,
        "kind": job.kind,
        "status": job.status,
        "progress": float(job.progress) if job.progress is not None else 0.0,
        "message": job.message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "result": (json.loads(job.result_json) if job.result_json else None),
    }


# --- Sync runners (used by tests + demo without Celery) ---

async def run_backtest_job_inline(session: AsyncSession, job: Job) -> None:
    """Execute a backtest job on the API session (no Celery required).

    This path is used by tests and by installations without a Redis
    broker. Same result shape as the Celery path.
    """
    from datetime import timedelta

    from app.models.asset import Asset
    from app.services.backtester import BacktestParams, run_backtest

    payload = json.loads(job.payload_json)
    await update_status(session, job, status=JobStatus.COLLECTING_DATA,
                         progress=0.15, message="loading bars")

    asset = (await session.execute(
        select(Asset).where(Asset.canonical_id == payload["asset_canonical_id"])
    )).scalar_one_or_none()
    if asset is None:
        await fail(session, job, message="asset not found")
        return

    await update_status(session, job, status=JobStatus.CALCULATING,
                         progress=0.4, message="walking forward")

    end = datetime.now(UTC)
    start = end - timedelta(days=int(payload.get("lookback_days", 365)))
    try:
        outcome = await run_backtest(session, BacktestParams(
            asset=asset,
            interval=payload.get("interval", "1d"),
            start=start, end=end,
            horizon=payload.get("horizon", "5D"),
            entry_threshold=float(payload.get("entry_threshold", 20.0)),
            exit_threshold=float(payload.get("exit_threshold", -5.0)),
            cost_bps_override=payload.get("cost_bps"),
            slippage_bps_override=payload.get("slippage_bps"),
        ))
    except Exception as e:  # noqa: BLE001
        await fail(session, job, message=f"{type(e).__name__}: {e}")
        return

    await update_status(session, job, status=JobStatus.GENERATING_REPORT,
                         progress=0.85, message="serializing")

    # Compact result shape (mirrors the sync backtest response).
    result = {
        "asset_canonical_id": asset.canonical_id,
        "horizon": outcome.params.horizon,
        "interval": outcome.params.interval,
        "metrics": _metrics_dict(outcome.metrics),
        "warnings": outcome.warnings,
        "trades_count": len(outcome.trades),
        "equity_len": len(outcome.equity),
    }
    await complete(session, job, result=result)


def _metrics_dict(m) -> dict:
    from dataclasses import asdict
    d = asdict(m)
    if d.get("profit_factor") == float("inf"):
        d["profit_factor"] = "inf"
    return d


# Silence unused-import lints
_ = JobKind
