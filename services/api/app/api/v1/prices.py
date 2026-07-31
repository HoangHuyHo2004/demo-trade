from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import RegistryDep, SessionDep
from app.domain.asset_id import AssetId
from app.models.asset import Asset
from app.schemas.common import BarOut, BarsOut, QuoteOut
from app.services.market_status import status_for

router = APIRouter()

_INTERVAL_PATTERN = r"^(1m|15m|1h|1d|1w|1mo)$"


async def _load_asset(session, asset_id: str) -> Asset:
    result = await session.execute(select(Asset).where(Asset.canonical_id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="asset not found")
    return asset


@router.get("/{asset_id:path}/quote", response_model=QuoteOut)
async def get_quote(
    asset_id: str,
    session: SessionDep,
    registry: RegistryDep,
) -> QuoteOut:
    asset = await _load_asset(session, asset_id)
    aid = AssetId.parse(asset.canonical_id)
    provider = registry.market_data_for(asset.market)
    q = await provider.get_quote(aid)
    market_state = "UNKNOWN"
    ms = status_for(asset.calendar)
    if ms is not None:
        market_state = ms.state
    is_stale = q.is_stale or (
        market_state == "CLOSED" and (datetime.now(UTC) - q.event_time) > timedelta(hours=24)
    )
    return QuoteOut(
        asset_id=asset.canonical_id,
        price=q.price,
        currency=q.currency,
        event_time=q.event_time,
        source=q.source,
        is_stale=is_stale,
        market_state=market_state,
    )


@router.get("/{asset_id:path}/bars", response_model=BarsOut)
async def get_bars(
    asset_id: str,
    session: SessionDep,
    registry: RegistryDep,
    interval: str = Query("1d", pattern=_INTERVAL_PATTERN),
    lookback_days: int = Query(365, ge=1, le=3650),
) -> BarsOut:
    asset = await _load_asset(session, asset_id)
    aid = AssetId.parse(asset.canonical_id)
    end = datetime.now(UTC)
    start = end - timedelta(days=lookback_days)
    provider = registry.market_data_for(asset.market)
    bars = await provider.get_bars(aid, interval=interval, start=start, end=end)
    return BarsOut(
        asset_id=asset.canonical_id,
        interval=interval,
        source=provider.slug,
        bars=[BarOut(t=b.bar_time, o=b.open, h=b.high, l=b.low, c=b.close, v=b.volume) for b in bars],
    )
