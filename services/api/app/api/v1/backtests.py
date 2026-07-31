from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.deps import CurrentUserDep, SessionDep
from app.models.asset import Asset
from app.models.signal import BacktestEquityPoint, BacktestRun, BacktestTrade
from app.services.backtester import BacktestParams, run_backtest
from app.services.jobs import (
    JobKind,
    create_job,
    job_to_dict,
    run_backtest_job_inline,
)
from app.services.signal_engine import _get_or_create_model_version, get_model

router = APIRouter()
log = get_logger(__name__)


class BacktestRequest(BaseModel):
    asset_canonical_id: str = Field(..., min_length=3, max_length=96)
    interval: str = Field("1d", pattern=r"^(1m|15m|1h|1d|1w|1mo)$")
    start: datetime | None = None
    end: datetime | None = None
    horizon: str = Field("5D", pattern=r"^(1D|5D|20D)$")
    model: str = Field("ensemble-v1", max_length=64)
    entry_threshold: float = Field(20.0, ge=-100.0, le=100.0)
    exit_threshold: float = Field(-5.0, ge=-100.0, le=100.0)
    cost_bps: float | None = Field(None, ge=0.0, le=500.0)
    slippage_bps: float | None = Field(None, ge=0.0, le=500.0)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_backtest(
    body: BacktestRequest, response: Response,
    session: SessionDep, user: CurrentUserDep,
) -> dict:
    """Enqueue a backtest job (spec §14).

    Returns 202 with ``{job_id, status}``. Poll ``GET /api/v1/jobs/{job_id}``
    for progress. When Celery is unavailable (tests / demo installs
    without Redis), the setting ``USE_SYNC_JOBS=true`` runs the job
    inline before responding so the response already contains the final
    result.
    """
    # Fast validation up-front so a broken request doesn't create a
    # dangling job row.
    asset = (await session.execute(
        select(Asset).where(Asset.canonical_id == body.asset_canonical_id)
    )).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="asset not found")
    try:
        get_model(body.model)
    except KeyError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    payload = {
        "asset_canonical_id": body.asset_canonical_id,
        "interval": body.interval,
        "horizon": body.horizon,
        "entry_threshold": body.entry_threshold,
        "exit_threshold": body.exit_threshold,
        "cost_bps": body.cost_bps,
        "slippage_bps": body.slippage_bps,
        "lookback_days": _lookback_days_from_range(body),
    }
    job = await create_job(
        session, kind=JobKind.BACKTEST.value,
        user_id=user.id, payload=payload,
    )

    settings = get_settings()
    if settings.use_sync_jobs:
        await run_backtest_job_inline(session, job)
        await session.refresh(job)
    else:
        try:
            # Late import so tests don't require celery installed.
            from worker.celery_app import app as celery_app
            celery_app.send_task(
                "worker.tasks.run_backtest_job",
                args=[job.public_id],
            )
        except Exception as e:  # noqa: BLE001
            # Celery unreachable → transparently fall back to inline so
            # a demo install without Redis still works.
            log.warning("celery_send_task_failed_fallback_sync", err=str(e))
            await run_backtest_job_inline(session, job)
            await session.refresh(job)

    response.headers["Location"] = f"/api/v1/jobs/{job.public_id}"
    return job_to_dict(job)


def _lookback_days_from_range(body: BacktestRequest) -> int:
    if body.start and body.end:
        return max(1, (body.end - body.start).days)
    return 365


@router.post("/sync", status_code=status.HTTP_201_CREATED)
async def create_backtest_sync(
    body: BacktestRequest, session: SessionDep, user: CurrentUserDep,
) -> dict:
    asset = (await session.execute(
        select(Asset).where(Asset.canonical_id == body.asset_canonical_id)
    )).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="asset not found")
    try:
        model = get_model(body.model)
    except KeyError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    params = BacktestParams(
        asset=asset, interval=body.interval, start=body.start, end=body.end,
        horizon=body.horizon, model_code=body.model,
        entry_threshold=body.entry_threshold, exit_threshold=body.exit_threshold,
        cost_bps_override=body.cost_bps, slippage_bps_override=body.slippage_bps,
    )
    try:
        outcome = await run_backtest(session, params)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    mv = await _get_or_create_model_version(session, model)
    metrics_dict = _metrics_to_dict(outcome.metrics)
    metrics_dict["warnings"] = outcome.warnings

    run = BacktestRun(
        asset_id=asset.id,
        model_version_id=mv.id,
        interval=params.interval,
        start_time=outcome.equity[0].bar_time if outcome.equity else datetime.now(UTC),
        end_time=outcome.equity[-1].bar_time if outcome.equity else datetime.now(UTC),
        cost_bps=Decimal(f"{(body.cost_bps if body.cost_bps is not None else outcome.cost_profile.fee_bps + outcome.cost_profile.tax_bps):.2f}"),
        slippage_bps=Decimal(f"{(body.slippage_bps if body.slippage_bps is not None else outcome.cost_profile.slippage_bps):.2f}"),
        horizon=params.horizon,
        params_json=json.dumps({
            "entry_threshold": params.entry_threshold,
            "exit_threshold": params.exit_threshold,
        }, sort_keys=True),
        metrics_json=json.dumps(metrics_dict, sort_keys=True, default=str),
        status="ok",
        created_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    for t in outcome.trades:
        session.add(BacktestTrade(
            run_id=run.id, side="long",
            entry_time=t.entry_time, entry_price=Decimal(f"{t.entry_price:.10f}"),
            exit_time=t.exit_time, exit_price=Decimal(f"{t.exit_price:.10f}"),
            bars_held=t.bars_held,
            pnl_pct=Decimal(f"{t.pnl_pct:.6f}"),
            cost_pct=Decimal(f"{t.cost_pct:.6f}"),
            reason=t.reason,
        ))
    for e in outcome.equity:
        session.add(BacktestEquityPoint(
            run_id=run.id, bar_time=e.bar_time,
            strategy_equity=Decimal(f"{e.strategy_equity:.10f}"),
            buy_hold_equity=Decimal(f"{e.buy_hold_equity:.10f}"),
            in_position=e.in_position,
        ))
    await session.commit()

    return _serialize_run(run, outcome)


@router.get("/{run_id}")
async def get_backtest(run_id: int, session: SessionDep) -> dict:
    run = (await session.execute(
        select(BacktestRun)
        .where(BacktestRun.id == run_id)
        .options(selectinload(BacktestRun.trades), selectinload(BacktestRun.equity))
    )).scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="backtest run not found")
    return {
        "id": run.id,
        "asset_id": run.asset_id,
        "interval": run.interval,
        "start_time": run.start_time.isoformat(),
        "end_time": run.end_time.isoformat(),
        "horizon": run.horizon,
        "cost_bps": str(run.cost_bps),
        "slippage_bps": str(run.slippage_bps),
        "status": run.status,
        "params": json.loads(run.params_json or "{}"),
        "metrics": json.loads(run.metrics_json or "{}"),
        "trades": [
            {
                "entry_time": t.entry_time.isoformat(),
                "entry_price": str(t.entry_price),
                "exit_time": t.exit_time.isoformat(),
                "exit_price": str(t.exit_price),
                "bars_held": t.bars_held,
                "pnl_pct": float(t.pnl_pct),
                "cost_pct": float(t.cost_pct),
                "reason": t.reason,
            }
            for t in run.trades
        ],
        "equity": [
            {
                "t": e.bar_time.isoformat(),
                "strategy": float(e.strategy_equity),
                "buy_hold": float(e.buy_hold_equity),
                "in_position": e.in_position,
            }
            for e in run.equity
        ],
    }


def _metrics_to_dict(m) -> dict:
    d = asdict(m)
    # Replace inf profit_factor with a string so JSON is valid.
    if d.get("profit_factor") == float("inf"):
        d["profit_factor"] = "inf"
    return d


def _serialize_run(run: BacktestRun, outcome) -> dict:
    return {
        "id": run.id,
        "asset_id": run.asset_id,
        "horizon": run.horizon,
        "interval": run.interval,
        "start_time": run.start_time.isoformat(),
        "end_time": run.end_time.isoformat(),
        "cost_bps": str(run.cost_bps),
        "slippage_bps": str(run.slippage_bps),
        "params": json.loads(run.params_json),
        "metrics": _metrics_to_dict(outcome.metrics),
        "warnings": outcome.warnings,
        "trades": [
            {
                "entry_time": t.entry_time.isoformat(),
                "entry_price": t.entry_price,
                "exit_time": t.exit_time.isoformat(),
                "exit_price": t.exit_price,
                "bars_held": t.bars_held,
                "pnl_pct": t.pnl_pct,
                "cost_pct": t.cost_pct,
                "reason": t.reason,
            }
            for t in outcome.trades
        ],
        "equity": [
            {
                "t": e.bar_time.isoformat(),
                "strategy": e.strategy_equity,
                "buy_hold": e.buy_hold_equity,
                "in_position": e.in_position,
            }
            for e in outcome.equity
        ],
    }
