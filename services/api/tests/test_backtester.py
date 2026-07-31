"""Backtester: no-lookahead invariant, reproducibility, sane metrics."""
from datetime import UTC, datetime, timedelta

import pytest

from app.models.asset import Asset
from app.services.backtester import BacktestParams, run_backtest


async def _seed_us_and_bench(session) -> Asset:
    asset = Asset(
        canonical_id="EQUITY:US:NASDAQ:AAPL",
        asset_type="EQUITY", market="US", exchange_code="NASDAQ",
        symbol="AAPL", display_symbol="AAPL", name="Apple",
        quote_currency="USD", market_timezone="America/New_York", calendar="XNYS",
    )
    bench = Asset(
        canonical_id="ETF:US:NYSE:SPY",
        asset_type="ETF", market="US", exchange_code="NYSE",
        symbol="SPY", display_symbol="SPY", name="S&P 500 ETF",
        quote_currency="USD", market_timezone="America/New_York", calendar="XNYS",
        is_benchmark=True,
    )
    session.add(asset); session.add(bench)
    await session.commit()
    await session.refresh(asset)
    return asset


@pytest.mark.asyncio
async def test_backtest_produces_metrics_and_equity(session):
    asset = await _seed_us_and_bench(session)
    end = datetime(2024, 6, 1, tzinfo=UTC)
    start = end - timedelta(days=365)
    outcome = await run_backtest(session, BacktestParams(
        asset=asset, interval="1d", start=start, end=end,
        horizon="5D",
    ))
    m = outcome.metrics
    # Sanity: metrics fields are all populated, no crashes.
    assert -1.0 < m.total_return < 100
    assert -0.5 < m.max_drawdown <= 1.0
    assert m.trades >= 0
    assert m.exposure >= 0
    assert outcome.equity, "expected an equity curve"
    # Buy-and-hold reference is populated and finite.
    assert isinstance(m.buy_hold_return, float)
    # Benchmark comparison filled because we seeded SPY.
    assert m.benchmark_return is not None


@pytest.mark.asyncio
async def test_backtest_is_deterministic(session):
    asset = await _seed_us_and_bench(session)
    end = datetime(2024, 6, 1, tzinfo=UTC)
    start = end - timedelta(days=200)
    p = BacktestParams(asset=asset, interval="1d", start=start, end=end, horizon="5D")
    a = await run_backtest(session, p)
    b = await run_backtest(session, p)
    assert a.metrics.total_return == b.metrics.total_return
    assert len(a.trades) == len(b.trades)
    assert [round(t.pnl_pct, 8) for t in a.trades] == \
           [round(t.pnl_pct, 8) for t in b.trades]


@pytest.mark.asyncio
async def test_backtester_never_touches_bars_after_decision_time(session, monkeypatch):
    """Instrument the model's `compute` to record the maximum bar_time
    passed in; assert it never exceeds the decision timestamp.
    """
    asset = await _seed_us_and_bench(session)
    end = datetime(2024, 6, 1, tzinfo=UTC)
    start = end - timedelta(days=200)

    seen_max: list[tuple[datetime, datetime]] = []

    from app.quant.ensemble import RuleBasedEnsemble
    original = RuleBasedEnsemble.compute

    def spy(self, si, *, horizon):
        if si.times:
            seen_max.append((max(si.times), si.as_of))
        return original(self, si, horizon=horizon)

    monkeypatch.setattr(RuleBasedEnsemble, "compute", spy)

    await run_backtest(session, BacktestParams(
        asset=asset, interval="1d", start=start, end=end, horizon="5D",
    ))
    assert seen_max, "model was never invoked"
    for last_bar_t, as_of in seen_max:
        assert last_bar_t <= as_of, (
            f"lookahead detected: bar_time={last_bar_t} > as_of={as_of}"
        )


@pytest.mark.asyncio
async def test_backtest_rejects_bad_horizon(session):
    asset = await _seed_us_and_bench(session)
    with pytest.raises(ValueError):
        await run_backtest(session, BacktestParams(
            asset=asset, interval="1d", horizon="7D",
        ))
