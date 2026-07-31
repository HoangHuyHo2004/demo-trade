from datetime import UTC, datetime, timedelta

import pytest

from app.domain.asset_id import AssetId
from app.providers.mock import MockMarketDataProvider

AAPL = AssetId.parse("EQUITY:US:NASDAQ:AAPL")
BTC = AssetId.parse("CRYPTO:COINBASE:BTC-USD")


@pytest.mark.asyncio
async def test_bars_are_deterministic():
    p = MockMarketDataProvider()
    end = datetime(2024, 6, 1, tzinfo=UTC)
    start = end - timedelta(days=30)
    a = await p.get_bars(AAPL, interval="1d", start=start, end=end)
    b = await p.get_bars(AAPL, interval="1d", start=start, end=end)
    assert len(a) == len(b) > 20
    for x, y in zip(a, b, strict=True):
        assert x.bar_time == y.bar_time
        assert x.open == y.open
        assert x.close == y.close


@pytest.mark.asyncio
async def test_bars_available_at_no_lookahead():
    p = MockMarketDataProvider()
    end = datetime(2024, 6, 1, tzinfo=UTC)
    start = end - timedelta(days=5)
    bars = await p.get_bars(AAPL, interval="1h", start=start, end=end)
    for b in bars:
        assert b.available_at > b.bar_time, "bars must not be available before their close"


@pytest.mark.asyncio
async def test_overlapping_windows_agree():
    p = MockMarketDataProvider()
    mid = datetime(2024, 5, 15, tzinfo=UTC)
    a = await p.get_bars(AAPL, interval="1d", start=mid - timedelta(days=10), end=mid)
    b = await p.get_bars(AAPL, interval="1d", start=mid - timedelta(days=5), end=mid + timedelta(days=5))
    overlap_a = {x.bar_time: x.close for x in a if x.bar_time in {y.bar_time for y in b}}
    overlap_b = {y.bar_time: y.close for y in b if y.bar_time in overlap_a}
    assert overlap_a and overlap_a == overlap_b, "same bar_time → same close across windows"


@pytest.mark.asyncio
async def test_crypto_currency_and_quote():
    p = MockMarketDataProvider()
    q = await p.get_quote(BTC)
    assert q.currency == "USD"
    assert q.price > 0
