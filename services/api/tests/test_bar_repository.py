"""BarRepository: DB-first read + provider fallback + upsert."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.asset import Asset
from app.models.ingest import BarIngestRun
from app.models.market_data import PriceBar
from app.providers.mock import MockMarketDataProvider
from app.services.bar_repository import BarRepository


async def _seed_btc(session) -> Asset:
    a = Asset(
        canonical_id="CRYPTO:COINBASE:BTC-USD",
        asset_type="CRYPTO", market="COINBASE", exchange_code="COINBASE",
        symbol="BTC-USD", display_symbol="BTC/USD", name="Bitcoin",
        quote_currency="USD", base_asset="BTC", quote_asset="USD",
        market_timezone="UTC", calendar="24x7",
    )
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


@pytest.mark.asyncio
async def test_first_fetch_populates_cache_and_records_run(session):
    asset = await _seed_btc(session)
    repo = BarRepository(session)
    provider = MockMarketDataProvider()

    end = datetime(2024, 6, 1, tzinfo=UTC)
    start = end - timedelta(days=45)
    result = await repo.get_or_fetch(asset, provider, interval="1d", start=start, end=end)

    assert result.from_cache is False
    assert result.source == "mock"
    assert len(result.bars) > 30

    persisted = (await session.execute(
        select(PriceBar).where(PriceBar.asset_id == asset.id)
    )).scalars().all()
    assert len(persisted) == len(result.bars)

    runs = (await session.execute(select(BarIngestRun))).scalars().all()
    assert len(runs) == 1
    run = runs[0]
    assert run.status == "ok"
    assert run.finished_at is not None
    assert run.bars_inserted > 0


@pytest.mark.asyncio
async def test_second_call_reads_from_cache(session):
    asset = await _seed_btc(session)
    repo = BarRepository(session)
    provider = MockMarketDataProvider()
    end = datetime(2024, 6, 1, tzinfo=UTC)
    start = end - timedelta(days=45)

    await repo.get_or_fetch(asset, provider, interval="1d", start=start, end=end)
    result2 = await repo.get_or_fetch(asset, provider, interval="1d", start=start, end=end)

    assert result2.from_cache is True
    assert result2.source == "mock"

    # Only one ingest run — the second call was served from cache.
    runs = (await session.execute(select(BarIngestRun))).scalars().all()
    assert len(runs) == 1
