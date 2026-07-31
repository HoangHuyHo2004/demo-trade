"""Coinbase Exchange (spot) public market-data adapter.

Uses the public REST endpoints — no API key required. Coinbase-specific
prices are kept per-exchange; we intentionally do not fabricate a
cross-exchange "canonical" spot price.

Docs: https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproducttrades
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx

from app.core.config import get_settings
from app.domain.asset_id import AssetId, AssetType, Market
from app.providers._http import check_allowlisted, get_json
from app.providers.base import BarDTO, MarketDataProvider, QuoteDTO


class CoinbaseProvider(MarketDataProvider):
    slug = "coinbase"
    supports_markets = ("COINBASE",)

    _GRANULARITY = {
        "1m": 60,
        "15m": 900,
        "1h": 3600,
        "1d": 86400,
    }

    def __init__(self, base_url: str | None = None, client: httpx.AsyncClient | None = None):
        self._base = (base_url or get_settings().coinbase_api_url).rstrip("/")
        # Only this host is reachable through the shared helper.
        self._allowed = {"api.exchange.coinbase.com"}
        # If a mock transport was passed in, don't add the allowlist gate —
        # tests will use a test host.
        self._client = client
        self._external = client is not None

    async def _client_ctx(self):
        if self._client is not None:
            return self._client, False
        c = httpx.AsyncClient(base_url=self._base, headers={"user-agent": "demo-trade/0.1"})
        return c, True

    def _url(self, path: str) -> str:
        return f"{self._base}{path}"

    async def get_quote(self, asset: AssetId) -> QuoteDTO:
        self._validate(asset)
        c, owned = await self._client_ctx()
        try:
            url = self._url(f"/products/{asset.symbol}/ticker")
            if not self._external:
                check_allowlisted(url, self._allowed)
            data = await get_json(c, url)
        finally:
            if owned:
                await c.aclose()

        # {"trade_id":..., "price":"63000.00", "size":"0.01", "time":"2026-08-01T00:00:00.123Z", ...}
        assert isinstance(data, dict), "coinbase ticker: expected object"
        price = Decimal(str(data["price"]))
        event_time = _parse_iso(data["time"])
        return QuoteDTO(
            asset_id=asset,
            price=price,
            currency=_quote_currency(asset),
            event_time=event_time,
            ingest_time=datetime.now(UTC),
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
        self._validate(asset)
        if interval not in self._GRANULARITY:
            raise ValueError(f"coinbase does not support interval={interval}")
        granularity = self._GRANULARITY[interval]

        # Coinbase caps candle windows to ~300 buckets — chunk if needed.
        max_bars = 300
        chunk_span = timedelta(seconds=granularity * max_bars)
        out: list[BarDTO] = []
        cursor = start
        c, owned = await self._client_ctx()
        try:
            while cursor < end:
                chunk_end = min(end, cursor + chunk_span)
                url = self._url(f"/products/{asset.symbol}/candles")
                if not self._external:
                    check_allowlisted(url, self._allowed)
                data = await get_json(
                    c,
                    url,
                    params={
                        "start": cursor.isoformat().replace("+00:00", "Z"),
                        "end": chunk_end.isoformat().replace("+00:00", "Z"),
                        "granularity": granularity,
                    },
                )
                assert isinstance(data, list), "coinbase candles: expected array"
                # Coinbase returns [ time, low, high, open, close, volume ]
                # newest-first; normalize to oldest-first BarDTO.
                for row in reversed(data):
                    t = datetime.fromtimestamp(int(row[0]), tz=UTC)
                    low, high, open_, close_, volume = (Decimal(str(x)) for x in row[1:6])
                    available = t + timedelta(seconds=granularity)
                    out.append(BarDTO(
                        asset_id=asset,
                        interval=interval,
                        bar_time=t,
                        open=open_,
                        high=high,
                        low=low,
                        close=close_,
                        adj_close=close_,   # spot crypto has no split/div adjustment
                        volume=volume,
                        event_time=available,
                        ingest_time=datetime.now(UTC),
                        available_at=available,
                        source=self.slug,
                    ))
                cursor = chunk_end
        finally:
            if owned:
                await c.aclose()

        # Dedup + sort (Coinbase can return an inclusive boundary twice)
        seen: set[datetime] = set()
        deduped: list[BarDTO] = []
        for b in out:
            if b.bar_time in seen:
                continue
            seen.add(b.bar_time)
            deduped.append(b)
        deduped.sort(key=lambda b: b.bar_time)
        return deduped

    @staticmethod
    def _validate(asset: AssetId) -> None:
        if asset.asset_type is not AssetType.CRYPTO or asset.market is not Market.COINBASE:
            raise ValueError(
                f"CoinbaseProvider only supports CRYPTO:COINBASE assets, got {asset}"
            )


def _quote_currency(asset: AssetId) -> str:
    if "-" in asset.symbol:
        return asset.symbol.split("-", 1)[1]
    return "USD"


def _parse_iso(s: str) -> datetime:
    # Coinbase emits like "2026-08-01T00:00:00.123456Z"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(UTC)
