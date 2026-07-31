"""Deterministic mock market-data provider.

Produces GBM-shaped OHLCV bars seeded by ``(canonical_id, bar_time)`` so
identical inputs always produce identical outputs. This is what powers
DEMO_MODE=true — the whole app must be usable without any credentials.
"""
from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.asset_id import AssetId, AssetType, Market
from app.providers.base import BarDTO, MarketDataProvider, QuoteDTO

# Per-asset "true" annual drift/vol, chosen to look realistic per class.
_CLASS_PARAMS = {
    AssetType.EQUITY: {"mu": 0.08, "sigma": 0.28, "base_vol_units": 3_000_000},
    AssetType.ETF:    {"mu": 0.07, "sigma": 0.16, "base_vol_units": 5_000_000},
    AssetType.CRYPTO: {"mu": 0.20, "sigma": 0.75, "base_vol_units": 20_000},
    AssetType.INDEX:  {"mu": 0.07, "sigma": 0.18, "base_vol_units": 0},
}

# Per-canonical anchor prices used as day-0 starting values.
_ANCHOR_PRICE = {
    "EQUITY:US:NASDAQ:AAPL":     Decimal("190.00"),
    "EQUITY:US:NASDAQ:MSFT":     Decimal("430.00"),
    "ETF:US:NYSE:SPY":           Decimal("540.00"),
    "EQUITY:VN:HOSE:VNM":        Decimal("70000"),   # VND
    "EQUITY:VN:HOSE:VIC":        Decimal("48000"),
    "INDEX:VN:HOSE:VNINDEX":     Decimal("1280"),
    "CRYPTO:COINBASE:BTC-USD":   Decimal("62000"),
    "CRYPTO:COINBASE:ETH-USD":   Decimal("3200"),
}

_INTERVAL_SECONDS = {
    "1m":  60,
    "15m": 15 * 60,
    "1h":  60 * 60,
    "1d":  24 * 60 * 60,
    "1w":  7 * 24 * 60 * 60,
    "1mo": 30 * 24 * 60 * 60,
}


def _seeded_rand(*parts: object) -> float:
    """Deterministic uniform [0,1) from arbitrary parts."""
    key = "|".join(str(p) for p in parts).encode()
    h = hashlib.blake2b(key, digest_size=8).digest()
    return int.from_bytes(h, "big") / 2**64


def _box_muller(u1: float, u2: float) -> float:
    # Guard u1 away from 0.
    u1 = max(u1, 1e-12)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def _anchor_price(asset: AssetId) -> Decimal:
    key = str(asset)
    if key in _ANCHOR_PRICE:
        return _ANCHOR_PRICE[key]
    # Fallback: derive a stable pseudo-price so unseeded assets still work.
    base = 20.0 + 200.0 * _seeded_rand(key, "anchor")
    return Decimal(f"{base:.2f}")


def _bars_per_year(interval: str) -> float:
    return 365.0 * 24 * 3600 / _INTERVAL_SECONDS[interval]


class MockMarketDataProvider(MarketDataProvider):
    slug = "mock"
    supports_markets = ("US", "VN", "COINBASE", "KRAKEN", "BINANCE")

    def __init__(self, *, now_fn=None) -> None:
        self._now = now_fn or (lambda: datetime.now(UTC))

    async def get_quote(self, asset: AssetId) -> QuoteDTO:
        # Use the most recent 1h bar as the current quote.
        end = self._now()
        start = end - timedelta(hours=6)
        bars = await self.get_bars(asset, interval="1h", start=start, end=end)
        last = bars[-1] if bars else None
        price = last.close if last else _anchor_price(asset)
        event_time = last.bar_time + timedelta(hours=1) if last else end
        return QuoteDTO(
            asset_id=asset,
            price=price,
            currency=_currency_for(asset),
            event_time=event_time,
            ingest_time=end,
            source=self.slug,
            is_stale=False,
        )

    async def get_bars(
        self,
        asset: AssetId,
        *,
        interval: str,
        start: datetime,
        end: datetime,
    ) -> list[BarDTO]:
        if interval not in _INTERVAL_SECONDS:
            raise ValueError(f"unsupported interval: {interval}")
        if end < start:
            return []

        params = _CLASS_PARAMS[asset.asset_type]
        mu = params["mu"]
        sigma = params["sigma"]
        base_vol = params["base_vol_units"]

        step_s = _INTERVAL_SECONDS[interval]
        n = max(0, int((end - start).total_seconds() // step_s) + 1)
        n = min(n, 5000)  # hard cap

        # Anchor the deterministic walk to a canonical epoch so that
        # requests for overlapping windows yield the same numbers.
        epoch = datetime(2020, 1, 1, tzinfo=UTC)
        dt_years = step_s / (365.0 * 24 * 3600)
        drift = (mu - 0.5 * sigma * sigma) * dt_years
        vol = sigma * math.sqrt(dt_years)

        # Rebuild the price from epoch → first bar for continuity.
        first_index = int((start - epoch).total_seconds() // step_s)
        price = float(_anchor_price(asset))
        for i in range(max(0, first_index)):
            u1 = _seeded_rand(str(asset), interval, i, "u1")
            u2 = _seeded_rand(str(asset), interval, i, "u2")
            z = _box_muller(u1, u2)
            price *= math.exp(drift + vol * z)

        bars: list[BarDTO] = []
        for k in range(n):
            i = first_index + k
            u1 = _seeded_rand(str(asset), interval, i, "u1")
            u2 = _seeded_rand(str(asset), interval, i, "u2")
            z = _box_muller(u1, u2)
            open_p = price
            price *= math.exp(drift + vol * z)
            close_p = price
            hi_extra = abs(z) * sigma * math.sqrt(dt_years) * open_p * 0.6
            high_p = max(open_p, close_p) + hi_extra * _seeded_rand(str(asset), i, "hi")
            low_p = min(open_p, close_p) - hi_extra * _seeded_rand(str(asset), i, "lo")
            vol_scale = 0.4 + 1.6 * _seeded_rand(str(asset), i, "v")
            volume = Decimal(str(round(base_vol * vol_scale, 4))) if base_vol else Decimal(0)

            bar_time = epoch + timedelta(seconds=i * step_s)
            available = bar_time + timedelta(seconds=step_s)  # available only after close
            bars.append(
                BarDTO(
                    asset_id=asset,
                    interval=interval,
                    bar_time=bar_time,
                    open=Decimal(f"{open_p:.6f}"),
                    high=Decimal(f"{high_p:.6f}"),
                    low=Decimal(f"{low_p:.6f}"),
                    close=Decimal(f"{close_p:.6f}"),
                    adj_close=Decimal(f"{close_p:.6f}"),
                    volume=volume,
                    event_time=available,
                    ingest_time=self._now(),
                    available_at=available,
                    source=self.slug,
                )
            )
        # Trim any bars that fall outside the requested [start, end] window.
        return [b for b in bars if start <= b.bar_time <= end]


def _currency_for(asset: AssetId) -> str:
    if asset.market is Market.VN:
        return "VND"
    if asset.market is Market.US:
        return "USD"
    # Crypto pairs like BTC-USD → quote is second half.
    if "-" in asset.symbol:
        return asset.symbol.split("-", 1)[1]
    return "USD"
