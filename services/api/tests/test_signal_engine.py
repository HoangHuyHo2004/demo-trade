"""Signal engine end-to-end (in-memory DB, mock provider)."""
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models.asset import Asset
from app.models.signal import Signal, SignalFactor
from app.services.signal_engine import calculate_signal


async def _seed(session, market="US", canonical="EQUITY:US:NASDAQ:AAPL",
                exchange="NASDAQ", symbol="AAPL", ccy="USD",
                calendar="XNYS", tz="America/New_York",
                is_benchmark=False) -> Asset:
    a = Asset(
        canonical_id=canonical, asset_type="EQUITY", market=market,
        exchange_code=exchange, symbol=symbol, display_symbol=symbol,
        name=symbol, quote_currency=ccy,
        market_timezone=tz, calendar=calendar, is_benchmark=is_benchmark,
    )
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


@pytest.mark.asyncio
async def test_signal_payload_shape_and_persistence(session):
    asset = await _seed(session)
    await _seed(session, canonical="ETF:US:NYSE:SPY", exchange="NYSE",
                symbol="SPY", is_benchmark=True)

    as_of = datetime(2024, 6, 1, tzinfo=UTC)
    res = await calculate_signal(
        session, asset=asset, horizon="5D", as_of=as_of, persist=True,
    )
    p = res.payload
    for k in (
        "asset_id", "as_of", "horizon", "classification", "score",
        "confidence", "risk", "expected_holding_days",
        "positive_factors", "negative_factors", "contradictions",
        "liquidity_warnings", "data_quality_score", "regime",
        "strategy_version", "data_version", "generated_at", "disclaimer",
    ):
        assert k in p, f"missing payload key: {k}"
    assert p["asset_id"] == asset.canonical_id
    assert p["strategy_version"] == "ensemble-v1"
    assert p["horizon"] == "5D"
    assert -100 <= p["score"] <= 100
    assert 0 <= p["confidence"] <= 1
    assert p["risk"] in {"LOW", "MODERATE", "HIGH", "SEVERE"}
    assert p["classification"] in {
        "STRONG_BULLISH", "BULLISH", "NEUTRAL", "BEARISH",
        "STRONG_BEARISH", "AVOID_HIGH_RISK", "INSUFFICIENT_DATA",
    }
    # persistence
    rows = (await session.execute(select(Signal))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.asset_id == asset.id
    factors = (await session.execute(select(SignalFactor))).scalars().all()
    assert len(factors) >= 3
    for f in factors:
        assert f.category in {"trend", "momentum", "volatility", "volume", "benchmark"}


@pytest.mark.asyncio
async def test_insufficient_data_short_history(session):
    asset = await _seed(session)
    # Extremely early as_of so mock has almost nothing available yet.
    res = await calculate_signal(
        session, asset=asset, horizon="1D",
        as_of=datetime(2020, 1, 3, tzinfo=UTC), persist=True,
        lookback_bars=5,
    )
    # With < 10 bars the payload forces INSUFFICIENT_DATA.
    if res.payload["classification"] == "INSUFFICIENT_DATA":
        assert res.payload["score"] == 0
        assert res.payload["confidence"] == 0
    else:
        # If the mock returned enough bars, at least data_quality is low.
        assert res.payload["data_quality_score"] <= 0.6


@pytest.mark.asyncio
async def test_signal_is_reproducible(session):
    asset = await _seed(session)
    as_of = datetime(2024, 3, 1, tzinfo=UTC)
    a = await calculate_signal(session, asset=asset, horizon="5D",
                               as_of=as_of, persist=False)
    b = await calculate_signal(session, asset=asset, horizon="5D",
                               as_of=as_of, persist=False)
    assert a.payload["score"] == b.payload["score"]
    assert a.payload["data_version"] == b.payload["data_version"]
    assert [f["code"] for f in a.payload["positive_factors"]] == \
           [f["code"] for f in b.payload["positive_factors"]]


@pytest.mark.asyncio
async def test_signal_horizon_validation(session):
    asset = await _seed(session)
    with pytest.raises(ValueError):
        await calculate_signal(session, asset=asset, horizon="4D",
                               as_of=datetime(2024, 6, 1, tzinfo=UTC))
