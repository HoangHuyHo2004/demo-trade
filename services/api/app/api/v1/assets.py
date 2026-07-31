"""Asset search + get-by-id + spec §10 nested aliases + compare endpoint."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.v1 import prices as prices_module
from app.api.v1 import signals as signals_module
from app.deps import RegistryDep, SessionDep
from app.models.asset import Asset
from app.schemas.common import AssetOut, BarsOut, QuoteOut
from app.services.bar_repository import BarRepository
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


class CompareRequest(BaseModel):
    asset_canonical_ids: list[str] = Field(..., min_length=2, max_length=5)
    interval: str = Field("1d", pattern=r"^(1m|15m|1h|1d|1w|1mo)$")
    lookback_days: int = Field(180, ge=1, le=3650)


@router.post("/compare")
async def compare_assets(
    body: CompareRequest, session: SessionDep, registry: RegistryDep,
) -> dict:
    """Aligned close series for 2-5 assets, rebased to 100.

    Warns when currencies differ so callers know the returns are
    comparable but the absolute prices are not.
    """
    end = datetime.now(UTC)
    start = end - timedelta(days=body.lookback_days)
    repo = BarRepository(session)
    series: list[dict] = []
    currencies: set[str] = set()
    warnings: list[str] = []

    for cid in body.asset_canonical_ids:
        asset = (await session.execute(
            select(Asset).where(Asset.canonical_id == cid)
        )).scalar_one_or_none()
        if asset is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"asset not found: {cid}")
        currencies.add(asset.quote_currency)
        provider = registry.market_data_for(asset.market)
        r = await repo.get_or_fetch(
            asset, provider, interval=body.interval, start=start, end=end,
        )
        closes = [float(b.close) for b in r.bars]
        first = closes[0] if closes else None
        rebased = ([100.0 * (c / first) for c in closes] if first else [])
        period_return = ((closes[-1] - first) / first) if (first and len(closes) >= 2) else None
        series.append({
            "asset_canonical_id": cid,
            "display_symbol": asset.display_symbol,
            "market": asset.market,
            "quote_currency": asset.quote_currency,
            "bar_count": len(closes),
            "period_return": period_return,
            "closes": closes,
            "rebased_to_100": rebased,
            "times": [b.bar_time.isoformat() for b in r.bars],
        })

    mixed = len(currencies) > 1
    if mixed:
        warnings.append(
            f"Mixed currencies ({', '.join(sorted(currencies))}). Return "
            f"comparisons are meaningful; absolute prices are not "
            f"currency-normalized."
        )

    return {
        "interval": body.interval,
        "lookback_days": body.lookback_days,
        "mixed_currencies": mixed,
        "currencies": sorted(currencies),
        "series": series,
        "warnings": warnings,
    }


@router.get("/{asset_id:path}", response_model=AssetOut)
async def get_asset(asset_id: str, session: SessionDep) -> Asset:
    """``asset_id`` is the canonical id (e.g. ``EQUITY:US:NASDAQ:AAPL``)."""
    result = await session.execute(select(Asset).where(Asset.canonical_id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="asset not found")
    return asset


# ---- Spec §10 nested aliases ----
# The canonical URLs remain /api/v1/prices/* and /api/v1/signals/*, but
# spec §10 also wants everything reachable under /api/v1/assets/{id}/*.
# These delegate to the existing handlers so there's one implementation.

@router.get("/{asset_id:path}/quote", response_model=QuoteOut)
async def asset_quote(
    asset_id: str, session: SessionDep, registry: RegistryDep,
) -> QuoteOut:
    return await prices_module.get_quote(asset_id, session, registry)


@router.get("/{asset_id:path}/bars", response_model=BarsOut)
async def asset_bars(
    asset_id: str, session: SessionDep, registry: RegistryDep,
    interval: str = Query("1d", pattern=r"^(1m|15m|1h|1d|1w|1mo)$"),
    lookback_days: int = Query(365, ge=1, le=3650),
) -> BarsOut:
    return await prices_module.get_bars(
        asset_id, session, registry, interval=interval,
        lookback_days=lookback_days,
    )


@router.get("/{asset_id:path}/signal")
async def asset_signal(
    asset_id: str, session: SessionDep,
    horizon: str = Query("5D", pattern=r"^(1D|5D|20D)$"),
    model: str = Query("ensemble-v1", max_length=64),
) -> dict:
    return await signals_module.get_signal(
        asset_id, session, horizon=horizon, model=model,
    )
