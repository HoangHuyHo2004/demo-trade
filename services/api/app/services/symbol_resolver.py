"""Symbol resolution — ambiguity-safe search across markets."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetAlias


async def search_assets(
    session: AsyncSession,
    *,
    query: str,
    market: str | None = None,
    asset_type: str | None = None,
    limit: int = 25,
) -> list[Asset]:
    q = query.strip().upper()
    if not q:
        return []
    stmt = select(Asset).where(
        or_(
            Asset.symbol.like(f"{q}%"),
            Asset.display_symbol.like(f"{q}%"),
            Asset.canonical_id.like(f"%{q}%"),
            Asset.name.ilike(f"%{query.strip()}%"),
            Asset.id.in_(
                select(AssetAlias.asset_id).where(AssetAlias.value.like(f"{q}%"))
            ),
        )
    )
    if market:
        stmt = stmt.where(Asset.market == market.upper())
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type.upper())
    stmt = stmt.order_by(Asset.canonical_id).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())
