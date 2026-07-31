"""Asset search + get-by-id."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import SessionDep
from app.models.asset import Asset
from app.schemas.common import AssetOut
from app.services.symbol_resolver import search_assets

router = APIRouter()


@router.get("/search", response_model=list[AssetOut])
async def search(
    session: SessionDep,
    q: str = Query(..., min_length=1, max_length=64),
    market: str | None = Query(None, pattern=r"^(US|VN|COINBASE|KRAKEN|BINANCE)$"),
    asset_type: str | None = Query(None, pattern=r"^(EQUITY|ETF|CRYPTO|INDEX)$"),
    limit: int = Query(25, ge=1, le=100),
) -> list[Asset]:
    return await search_assets(
        session, query=q, market=market, asset_type=asset_type, limit=limit
    )


@router.get("/{asset_id:path}", response_model=AssetOut)
async def get_asset(asset_id: str, session: SessionDep) -> Asset:
    """``asset_id`` is the canonical id (e.g. ``EQUITY:US:NASDAQ:AAPL``)."""
    result = await session.execute(select(Asset).where(Asset.canonical_id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="asset not found")
    return asset
