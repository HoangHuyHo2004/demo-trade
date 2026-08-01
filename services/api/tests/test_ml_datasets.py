"""Dataset builder: point-in-time correctness, versioning, walk-forward folds."""
from datetime import UTC, datetime, timedelta

import pytest

from app.ml.datasets import (
    BuildParams,
    build_dataset,
    compute_dataset_version,
    make_walk_forward_folds,
)
from app.models.asset import Asset
from app.models.market_data import PriceBar


async def _seed_asset_with_bars(
    session, canonical_id: str, market: str, n_bars: int = 260,
    start: datetime | None = None, available_lag_days: int = 0,
) -> Asset:
    a = Asset(
        canonical_id=canonical_id, asset_type="EQUITY", market=market,
        exchange_code="NASDAQ" if market == "US" else "HOSE",
        symbol=canonical_id.split(":")[-1], display_symbol=canonical_id.split(":")[-1],
        name=canonical_id, quote_currency="USD" if market == "US" else "VND",
        market_timezone="America/New_York" if market == "US" else "Asia/Ho_Chi_Minh",
        calendar="XNYS" if market == "US" else "XHOS",
    )
    session.add(a)
    await session.commit()
    await session.refresh(a)

    start = start or datetime(2024, 1, 1, tzinfo=UTC)
    price = 100.0
    for i in range(n_bars):
        price *= 1.0005
        bar_time = start + timedelta(days=i)
        available = bar_time + timedelta(days=available_lag_days)
        session.add(PriceBar(
            asset_id=a.id, interval="1d", bar_time=bar_time,
            open=price, high=price * 1.01, low=price * 0.99, close=price,
            volume=1_000_000, source="test",
            event_time=bar_time, ingest_time=bar_time, available_at=available,
        ))
    await session.commit()
    return a


@pytest.mark.asyncio
async def test_build_dataset_produces_rows(session):
    await _seed_asset_with_bars(session, "EQUITY:US:NASDAQ:AAPL", "US", n_bars=260)
    table = await build_dataset(
        session, BuildParams(market="US", horizon_bars=5, warmup_bars=60),
    )
    assert len(table.rows) > 0
    assert table.market == "US"
    for r in table.rows:
        assert r["direction"] in (-1, 0, 1)
        assert "future_return" in r


@pytest.mark.asyncio
async def test_dataset_excludes_bars_not_yet_available(session):
    """Point-in-time correctness: bars whose available_at is AFTER the
    requested to_time must never appear in the built dataset."""
    start = datetime(2024, 1, 1, tzinfo=UTC)
    await _seed_asset_with_bars(
        session, "EQUITY:US:NASDAQ:MSFT", "US", n_bars=100,
        start=start, available_lag_days=0,
    )
    # to_time cuts off well before the last bar's available_at
    cutoff = start + timedelta(days=50)
    table = await build_dataset(
        session, BuildParams(
            market="US", horizon_bars=5, warmup_bars=20, to_time=cutoff,
        ),
    )
    for r in table.rows:
        bar_time = datetime.fromisoformat(r["bar_time"])
        assert bar_time <= cutoff


@pytest.mark.asyncio
async def test_dataset_version_is_deterministic(session):
    await _seed_asset_with_bars(session, "EQUITY:US:NASDAQ:AAPL", "US", n_bars=200)
    p = BuildParams(market="US", horizon_bars=5, warmup_bars=60)
    t1 = await build_dataset(session, p)
    t2 = await build_dataset(session, p)
    assert t1.dataset_version == t2.dataset_version


def test_dataset_version_changes_with_params():
    universe = ["EQUITY:US:NASDAQ:AAPL"]
    v1 = compute_dataset_version("US", "1d", 5, 5.0, None, None, universe)
    v2 = compute_dataset_version("US", "1d", 20, 5.0, None, None, universe)
    v3 = compute_dataset_version("US", "1d", 5, 10.0, None, None, universe)
    assert v1 != v2
    assert v1 != v3


@pytest.mark.asyncio
async def test_build_dataset_raises_on_empty_universe(session):
    with pytest.raises(ValueError):
        await build_dataset(session, BuildParams(market="VN", horizon_bars=5))


# ---------- walk-forward folds ----------

def test_walk_forward_folds_are_chronological_and_non_overlapping():
    start = datetime(2020, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 1, tzinfo=UTC)
    folds = make_walk_forward_folds(
        start=start, end=end, train_days=365, val_days=90, test_days=90, embargo_days=5,
    )
    assert len(folds) > 0
    for f in folds:
        assert f.train_from == start
        assert f.train_to <= f.val_from
        assert f.val_to <= (f.test_from or end)
        if f.test_from:
            assert f.val_to < f.test_from  # embargo gap enforced
            assert f.test_from < f.test_to


def test_walk_forward_folds_train_window_expands():
    start = datetime(2020, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 1, tzinfo=UTC)
    folds = make_walk_forward_folds(
        start=start, end=end, train_days=365, val_days=90, test_days=0, embargo_days=5,
    )
    assert len(folds) >= 2
    for i in range(1, len(folds)):
        assert folds[i].train_to > folds[i - 1].train_to  # expanding window


def test_walk_forward_folds_empty_when_insufficient_history():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 3, 1, tzinfo=UTC)  # only 2 months
    folds = make_walk_forward_folds(
        start=start, end=end, train_days=365, val_days=90, test_days=90,
    )
    assert folds == []
