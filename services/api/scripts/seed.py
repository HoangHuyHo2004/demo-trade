"""Idempotent demo-data seed.

Creates:
  * A demo user (email from settings)
  * Exchanges (NASDAQ, NYSE, HOSE, HNX, UPCOM, COINBASE)
  * A cross-market asset set including per-market benchmarks
  * A default watchlist populated with one asset per market
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db import SessionLocal
from app.models.asset import Asset
from app.models.exchange import Exchange
from app.models.user import User
from app.models.watchlist import Watchlist, WatchlistItem


@dataclass(frozen=True)
class ExchangeSeed:
    code: str
    name: str
    market: str
    timezone: str
    calendar: str


@dataclass(frozen=True)
class AssetSeed:
    canonical_id: str
    asset_type: str
    market: str
    exchange_code: str
    symbol: str
    display_symbol: str
    name: str
    quote_currency: str
    market_timezone: str
    calendar: str
    is_benchmark: bool = False
    base_asset: str | None = None
    quote_asset: str | None = None


EXCHANGES = [
    ExchangeSeed("NASDAQ",   "Nasdaq Stock Market",           "US", "America/New_York",  "XNYS"),
    ExchangeSeed("NYSE",     "New York Stock Exchange",       "US", "America/New_York",  "XNYS"),
    ExchangeSeed("HOSE",     "Ho Chi Minh Stock Exchange",    "VN", "Asia/Ho_Chi_Minh",  "XHOS"),
    ExchangeSeed("HNX",      "Hanoi Stock Exchange",          "VN", "Asia/Ho_Chi_Minh",  "XHNX"),
    ExchangeSeed("UPCOM",    "UPCoM (VN)",                    "VN", "Asia/Ho_Chi_Minh",  "UPCOM"),
    ExchangeSeed("COINBASE", "Coinbase (spot)",         "COINBASE", "UTC",               "24x7"),
]


ASSETS = [
    # US equities + benchmark ETF
    AssetSeed("EQUITY:US:NASDAQ:AAPL",   "EQUITY", "US", "NASDAQ", "AAPL", "AAPL",
              "Apple Inc.", "USD", "America/New_York", "XNYS"),
    AssetSeed("EQUITY:US:NASDAQ:MSFT",   "EQUITY", "US", "NASDAQ", "MSFT", "MSFT",
              "Microsoft Corp.", "USD", "America/New_York", "XNYS"),
    AssetSeed("ETF:US:NYSE:SPY",         "ETF",    "US", "NYSE",   "SPY",  "SPY",
              "SPDR S&P 500 ETF (benchmark)", "USD", "America/New_York", "XNYS", is_benchmark=True),

    # VN equities + benchmark index
    AssetSeed("EQUITY:VN:HOSE:VNM",      "EQUITY", "VN", "HOSE",   "VNM",  "VNM",
              "Vinamilk", "VND", "Asia/Ho_Chi_Minh", "XHOS"),
    AssetSeed("EQUITY:VN:HOSE:VIC",      "EQUITY", "VN", "HOSE",   "VIC",  "VIC",
              "Vingroup", "VND", "Asia/Ho_Chi_Minh", "XHOS"),
    AssetSeed("INDEX:VN:HOSE:VNINDEX",   "INDEX",  "VN", "HOSE",   "VNINDEX", "VN-Index",
              "Ho Chi Minh Stock Index (benchmark)", "VND",
              "Asia/Ho_Chi_Minh", "XHOS", is_benchmark=True),

    # Crypto
    AssetSeed("CRYPTO:COINBASE:BTC-USD", "CRYPTO", "COINBASE", "COINBASE", "BTC-USD", "BTC/USD",
              "Bitcoin (Coinbase spot)", "USD", "UTC", "24x7",
              base_asset="BTC", quote_asset="USD", is_benchmark=True),
    AssetSeed("CRYPTO:COINBASE:ETH-USD", "CRYPTO", "COINBASE", "COINBASE", "ETH-USD", "ETH/USD",
              "Ethereum (Coinbase spot)", "USD", "UTC", "24x7",
              base_asset="ETH", quote_asset="USD"),
]

# One canonical asset per market → default watchlist starter.
DEFAULT_WATCHLIST_ITEMS = [
    "EQUITY:US:NASDAQ:AAPL",
    "EQUITY:VN:HOSE:VNM",
    "CRYPTO:COINBASE:BTC-USD",
]


async def main() -> None:
    configure_logging()
    log = get_logger("seed")
    settings = get_settings()

    async with SessionLocal() as session:
        # exchanges
        for e in EXCHANGES:
            existing = await session.execute(select(Exchange).where(Exchange.code == e.code))
            if existing.scalar_one_or_none() is None:
                session.add(Exchange(
                    code=e.code, name=e.name, market=e.market,
                    timezone=e.timezone, calendar=e.calendar,
                ))
        await session.commit()

        # assets
        for a in ASSETS:
            existing = await session.execute(
                select(Asset).where(Asset.canonical_id == a.canonical_id)
            )
            if existing.scalar_one_or_none() is None:
                session.add(Asset(
                    canonical_id=a.canonical_id,
                    asset_type=a.asset_type,
                    market=a.market,
                    exchange_code=a.exchange_code,
                    symbol=a.symbol,
                    display_symbol=a.display_symbol,
                    name=a.name,
                    quote_currency=a.quote_currency,
                    base_asset=a.base_asset,
                    quote_asset=a.quote_asset,
                    market_timezone=a.market_timezone,
                    calendar=a.calendar,
                    is_benchmark=a.is_benchmark,
                ))
        await session.commit()

        # user
        result = await session.execute(select(User).where(User.email == settings.api_demo_user_email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(email=settings.api_demo_user_email, display_name="Demo User")
            session.add(user)
            await session.commit()
            await session.refresh(user)
        # In demo mode the seeded user is also the admin so /ml/train etc.
        # is exercisable end-to-end. In production DEMO_MODE=false + a real
        # admin promotion process would replace this.
        if settings.demo_mode and not user.is_admin:
            user.is_admin = True
            await session.commit()

        # watchlist
        result = await session.execute(
            select(Watchlist).where(Watchlist.user_id == user.id, Watchlist.name == "Default")
        )
        wl = result.scalar_one_or_none()
        if wl is None:
            wl = Watchlist(user_id=user.id, name="Default")
            session.add(wl)
            await session.commit()
            await session.refresh(wl)

        for canonical in DEFAULT_WATCHLIST_ITEMS:
            asset_res = await session.execute(select(Asset).where(Asset.canonical_id == canonical))
            asset = asset_res.scalar_one_or_none()
            if asset is None:
                continue
            item_res = await session.execute(
                select(WatchlistItem).where(
                    WatchlistItem.watchlist_id == wl.id,
                    WatchlistItem.asset_id == asset.id,
                )
            )
            if item_res.scalar_one_or_none() is None:
                session.add(WatchlistItem(watchlist_id=wl.id, asset_id=asset.id))
        await session.commit()

        log.info("seed_complete", user=user.email, watchlist=wl.name)


if __name__ == "__main__":
    asyncio.run(main())
