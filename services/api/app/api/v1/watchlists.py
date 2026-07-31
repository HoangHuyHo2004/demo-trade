from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.deps import CurrentUserDep, SessionDep
from app.models.asset import Asset
from app.models.watchlist import Watchlist, WatchlistItem
from app.schemas.common import AssetOut, ORMBase

router = APIRouter()


class WatchlistItemOut(ORMBase):
    id: int
    note: str
    asset: AssetOut


class WatchlistOut(ORMBase):
    id: int
    name: str
    items: list[WatchlistItemOut]


class WatchlistCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class WatchlistItemCreate(BaseModel):
    asset_canonical_id: str = Field(..., min_length=3, max_length=96)
    note: str = Field(default="", max_length=500)


@router.get("", response_model=list[WatchlistOut])
async def list_watchlists(session: SessionDep, user: CurrentUserDep) -> list[Watchlist]:
    stmt = (
        select(Watchlist)
        .where(Watchlist.user_id == user.id)
        .options(selectinload(Watchlist.items).selectinload(WatchlistItem.asset))
        .order_by(Watchlist.name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().unique().all())


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    body: WatchlistCreate,
    session: SessionDep,
    user: CurrentUserDep,
) -> Watchlist:
    wl = Watchlist(user_id=user.id, name=body.name)
    session.add(wl)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="watchlist name already exists") from e
    await session.refresh(wl, attribute_names=["items"])
    return wl


@router.post(
    "/{watchlist_id}/items",
    response_model=WatchlistItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_item(
    watchlist_id: int,
    body: WatchlistItemCreate,
    session: SessionDep,
    user: CurrentUserDep,
) -> WatchlistItem:
    wl = await _load_owned_watchlist(session, watchlist_id, user.id)
    asset = await session.execute(
        select(Asset).where(Asset.canonical_id == body.asset_canonical_id)
    )
    asset_obj = asset.scalar_one_or_none()
    if asset_obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="asset not found")
    item = WatchlistItem(watchlist_id=wl.id, asset_id=asset_obj.id, note=body.note)
    session.add(item)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="asset already on watchlist") from e
    await session.refresh(item)
    # Load asset for response.
    item.asset = asset_obj  # type: ignore[attr-defined]
    return item


@router.post(
    "/{watchlist_id}/assets",
    response_model=WatchlistItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_asset_alias(
    watchlist_id: int, body: WatchlistItemCreate,
    session: SessionDep, user: CurrentUserDep,
) -> WatchlistItem:
    """Spec §10 alias of POST /items — same body, same behavior."""
    return await add_item(watchlist_id, body, session, user)


@router.delete(
    "/{watchlist_id}/assets/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_asset_alias(
    watchlist_id: int, item_id: int,
    session: SessionDep, user: CurrentUserDep,
) -> None:
    """Spec §10 alias of DELETE /items/{id}."""
    await remove_item(watchlist_id, item_id, session, user)


@router.delete("/{watchlist_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(
    watchlist_id: int,
    item_id: int,
    session: SessionDep,
    user: CurrentUserDep,
) -> None:
    wl = await _load_owned_watchlist(session, watchlist_id, user.id)
    result = await session.execute(
        select(WatchlistItem).where(
            WatchlistItem.id == item_id, WatchlistItem.watchlist_id == wl.id
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="item not found")
    await session.delete(item)
    await session.commit()


async def _load_owned_watchlist(session, watchlist_id: int, user_id: int) -> Watchlist:
    result = await session.execute(
        select(Watchlist).where(Watchlist.id == watchlist_id, Watchlist.user_id == user_id)
    )
    wl = result.scalar_one_or_none()
    if wl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="watchlist not found")
    return wl
