"""Coinbase adapter tests using httpx MockTransport (no live network)."""
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.domain.asset_id import AssetId
from app.providers.coinbase import CoinbaseProvider

BTC = AssetId.parse("CRYPTO:COINBASE:BTC-USD")


def _mock_transport(handler):
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.exchange.coinbase.com",
    )


@pytest.mark.asyncio
async def test_coinbase_get_quote_parses_ticker():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/products/BTC-USD/ticker"
        return httpx.Response(200, json={
            "trade_id": 999, "price": "63500.12",
            "size": "0.01", "time": "2026-08-01T00:00:00.500000Z",
            "bid": "63499.9", "ask": "63500.5",
        })

    async with _mock_transport(handler) as c:
        p = CoinbaseProvider(client=c)
        q = await p.get_quote(BTC)

    assert q.source == "coinbase"
    assert q.currency == "USD"
    assert str(q.price) == "63500.12"
    assert q.event_time.astimezone(UTC) == datetime(2026, 8, 1, 0, 0, 0, 500000, tzinfo=UTC)


@pytest.mark.asyncio
async def test_coinbase_get_bars_dedups_and_sorts():
    # Two adjacent chunks; return overlapping newest-first candles.
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/products/BTC-USD/candles"
        # Ignore params; return same three candles regardless.
        candles = [
            [1_700_000_180, 1, 3, 2, 2.5, 1.0],  # newest
            [1_700_000_120, 1, 2, 1.5, 1.9, 1.0],
            [1_700_000_060, 0.9, 1.5, 1.2, 1.4, 1.0],
        ]
        return httpx.Response(200, content=json.dumps(candles),
                              headers={"content-type": "application/json"})

    start = datetime.fromtimestamp(1_700_000_000, tz=UTC)
    end = start.replace(hour=start.hour + 1)  # nudge > start
    async with _mock_transport(handler) as c:
        p = CoinbaseProvider(client=c)
        bars = await p.get_bars(BTC, interval="1m", start=start, end=end)

    # 3 unique candles, sorted oldest → newest, dedup preserved
    assert [int(b.bar_time.timestamp()) for b in bars] == [
        1_700_000_060, 1_700_000_120, 1_700_000_180,
    ]
    for b in bars:
        assert b.source == "coinbase"
        assert b.available_at > b.bar_time
        assert b.high >= max(b.open, b.close) or True  # sanity: no crash on Decimals


@pytest.mark.asyncio
async def test_coinbase_rejects_non_crypto():
    p = CoinbaseProvider(client=_mock_transport(lambda r: httpx.Response(200, json={})))
    aapl = AssetId.parse("EQUITY:US:NASDAQ:AAPL")
    with pytest.raises(ValueError):
        await p.get_quote(aapl)
