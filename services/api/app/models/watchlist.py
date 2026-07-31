from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._mixins import TimestampMixin
from app.models.asset import Asset


class Watchlist(Base, TimestampMixin):
    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    items: Mapped[list[WatchlistItem]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistItem(Base, TimestampMixin):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "asset_id", name="uq_watchlist_items_wl_asset"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"), index=True, nullable=False
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    note: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    watchlist: Mapped[Watchlist] = relationship(back_populates="items")
    asset: Mapped[Asset] = relationship(lazy="joined")
