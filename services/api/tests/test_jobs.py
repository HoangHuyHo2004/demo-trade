"""Async job pattern (spec §14)."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.asset import Asset
from app.models.job import Job, JobKind, JobStatus
from app.services.jobs import (
    complete,
    create_job,
    job_to_dict,
    load_job,
    run_backtest_job_inline,
    update_status,
)


async def _seed_asset(session, canonical="EQUITY:US:NASDAQ:AAPL") -> Asset:
    a = Asset(
        canonical_id=canonical, asset_type="EQUITY", market="US",
        exchange_code="NASDAQ", symbol="AAPL", display_symbol="AAPL",
        name="Apple", quote_currency="USD",
        market_timezone="America/New_York", calendar="XNYS",
    )
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


@pytest.mark.asyncio
async def test_create_job_generates_public_id(session):
    job = await create_job(
        session, kind=JobKind.BACKTEST.value, user_id=None,
        payload={"asset_canonical_id": "EQUITY:US:NASDAQ:AAPL"},
    )
    assert job.public_id.startswith("backtest_")
    assert job.status == JobStatus.QUEUED.value
    assert float(job.progress) == 0.0
    assert job.result_json is None


@pytest.mark.asyncio
async def test_load_job_roundtrip(session):
    job = await create_job(session, kind=JobKind.BACKTEST.value,
                            user_id=None, payload={})
    fetched = await load_job(session, job.public_id)
    assert fetched is not None
    assert fetched.id == job.id


@pytest.mark.asyncio
async def test_update_status_transitions(session):
    job = await create_job(session, kind=JobKind.BACKTEST.value,
                            user_id=None, payload={})
    await update_status(session, job, status=JobStatus.CALCULATING,
                         progress=0.5, message="halfway")
    assert job.status == "CALCULATING"
    assert float(job.progress) == 0.5
    assert job.started_at is not None
    assert job.finished_at is None

    await complete(session, job, result={"ok": True})
    assert job.status == "COMPLETE"
    assert float(job.progress) == 1.0
    assert job.finished_at is not None
    assert '"ok"' in (job.result_json or "")


@pytest.mark.asyncio
async def test_inline_backtest_runner_end_to_end(session):
    asset = await _seed_asset(session)
    # Also seed the SPY benchmark so the backtester's alignment logic
    # has something to compare against.
    session.add(Asset(
        canonical_id="ETF:US:NYSE:SPY", asset_type="ETF", market="US",
        exchange_code="NYSE", symbol="SPY", display_symbol="SPY", name="SPY",
        quote_currency="USD", market_timezone="America/New_York",
        calendar="XNYS", is_benchmark=True,
    ))
    await session.commit()

    job = await create_job(
        session, kind=JobKind.BACKTEST.value, user_id=None,
        payload={
            "asset_canonical_id": asset.canonical_id,
            "interval": "1d",
            "horizon": "5D",
            "entry_threshold": 20.0,
            "exit_threshold": -5.0,
            "lookback_days": 365,
        },
    )
    await run_backtest_job_inline(session, job)
    assert job.status == "COMPLETE"
    d = job_to_dict(job)
    assert d["result"]["metrics"]["trades"] >= 0
    assert d["progress"] == 1.0


@pytest.mark.asyncio
async def test_inline_runner_fails_gracefully_on_missing_asset(session):
    job = await create_job(
        session, kind=JobKind.BACKTEST.value, user_id=None,
        payload={"asset_canonical_id": "EQUITY:US:NASDAQ:NOPE"},
    )
    await run_backtest_job_inline(session, job)
    assert job.status == "FAILED"
    assert "asset not found" in job.message


@pytest.mark.asyncio
async def test_jobs_endpoint_returns_job(session, client):
    await _seed_asset(session)
    # Also seed benchmark asset (backtester needs it for compare metrics)
    session.add(Asset(
        canonical_id="ETF:US:NYSE:SPY", asset_type="ETF", market="US",
        exchange_code="NYSE", symbol="SPY", display_symbol="SPY", name="SPY",
        quote_currency="USD", market_timezone="America/New_York",
        calendar="XNYS", is_benchmark=True,
    ))
    await session.commit()

    r = await client.post("/api/v1/backtests", json={
        "asset_canonical_id": "EQUITY:US:NASDAQ:AAPL",
        "interval": "1d",
        "horizon": "5D",
    })
    assert r.status_code == 202, r.text
    body = r.json()
    r2 = await client.get(f"/api/v1/jobs/{body['job_id']}")
    assert r2.status_code == 200
    j = r2.json()
    assert j["status"] == "COMPLETE"
    assert j["result"] is not None


# Silence unused-import lints
_ = datetime, timedelta, UTC, select, Job
