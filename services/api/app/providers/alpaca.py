"""Alpaca US-equities market-data adapter (Phase 2 skeleton).

Alpaca offers a free IEX-only tier that still requires an API key + secret.
Because the platform-agreement rules and data-redistribution terms vary
by subscription level, this adapter refuses to serve data unless
credentials are present. See ``docs/data-licensing-checklist.md``.

Only ``get_quote`` and ``get_bars`` are implemented. When credentials
are absent the registry will not select this adapter and the mock
provider is used instead.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.asset_id import AssetId, AssetType, Market
from app.providers._http import check_allowlisted, get_json
from app.providers.base import BarDTO, MarketDataProvider, QuoteDTO

log = get_logger(__name__)

_INTERVAL_MAP = {
    "1m": "1Min",
    "15m": "15Min",
    "1h": "1Hour",
    "1d": "1Day",
    "1w": "1Week",
    "1mo": "1Month",
}


class AlpacaProvider(MarketDataProvider):
    slug = "alpaca"
    supports_markets = ("US",)

    def __init__(self, client: httpx.AsyncClient | None = None):
        s = get_settings()
        self._base = s.alpaca_api_url.rstrip("/")
        self._headers = {
            "APCA-API-KEY-ID": s.alpaca_api_key,
            "APCA-API-SECRET-KEY": s.alpaca_api_secret,
            "user-agent": "demo-trade/0.1",
        }
        self._allowed = {"data.alpaca.markets"}
        self._client = client
        self._external = client is not None
        if not s.alpaca_api_key or not s.alpaca_api_secret:
            log.info("alpaca_skipped_missing_creds")

    async def _client_ctx(self):
        if self._client is not None:
            return self._client, False
        c = httpx.AsyncClient(base_url=self._base, headers=self._headers)
        return c, True

    async def get_quote(self, asset: AssetId) -> QuoteDTO:
        self._validate(asset)
        c, owned = await self._client_ctx()
        try:
            url = f"{self._base}/v2/stocks/{asset.symbol}/quotes/latest"
            if not self._external:
                check_allowlisted(url, self._allowed)
            data = await get_json(c, url)
        finally:
            if owned:
                await c.aclose()
        assert isinstance(data, dict)
        quote = data.get("quote", {})
        # bid/ask midpoint as the "price" for the last-known quote
        bp = Decimal(str(quote.get("bp", "0")))
        ap = Decimal(str(quote.get("ap", "0")))
        price = (bp + ap) / 2 if bp and ap else max(bp, ap)
        return QuoteDTO(
            asset_id=asset,
            price=price,
            currency="USD",
            event_time=_parse_iso(quote.get("t", "")),
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
        if interval not in _INTERVAL_MAP:
            raise ValueError(f"alpaca does not support interval={interval}")
        c, owned = await self._client_ctx()
        try:
            url = f"{self._base}/v2/stocks/{asset.symbol}/bars"
            if not self._external:
                check_allowlisted(url, self._allowed)
            data = await get_json(
                c, url,
                params={
                    "timeframe": _INTERVAL_MAP[interval],
                    "start": start.isoformat().replace("+00:00", "Z"),
                    "end": end.isoformat().replace("+00:00", "Z"),
                    "adjustment": "raw",
                    "feed": "iex",
                    "limit": 10000,
                },
            )
        finally:
            if owned:
                await c.aclose()
        assert isinstance(data, dict)
        out: list[BarDTO] = []
        for row in data.get("bars", []) or []:
            t = _parse_iso(row["t"])
            out.append(BarDTO(
                asset_id=asset,
                interval=interval,
                bar_time=t,
                open=Decimal(str(row["o"])), high=Decimal(str(row["h"])),
                low=Decimal(str(row["l"])), close=Decimal(str(row["c"])),
                adj_close=Decimal(str(row["c"])),
                volume=Decimal(str(row.get("v", 0))),
                event_time=t, ingest_time=datetime.now(UTC), available_at=t,
                source=self.slug,
            ))
        out.sort(key=lambda b: b.bar_time)
        return out

    @staticmethod
    def _validate(asset: AssetId) -> None:
        if asset.market is not Market.US or asset.asset_type not in {AssetType.EQUITY, AssetType.ETF}:
            raise ValueError(f"AlpacaProvider only supports US equities/ETFs, got {asset}")


def _parse_iso(s: str) -> datetime:
    if not s:
        return datetime.now(UTC)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s).astimezone(UTC)
