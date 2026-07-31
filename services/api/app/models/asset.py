from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._mixins import TimestampMixin


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("canonical_id", name="uq_assets_canonical_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_id: Mapped[str] = mapped_column(String(96), unique=True, index=True, nullable=False)

    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    exchange_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_symbol: Mapped[str] = mapped_column(String(32), nullable=False)

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    base_asset: Mapped[str | None] = mapped_column(String(16), nullable=True)
    quote_asset: Mapped[str | None] = mapped_column(String(16), nullable=True)
    market_timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    calendar: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_benchmark: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    aliases: Mapped[list[AssetAlias]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class AssetAlias(Base, TimestampMixin):
    """Alternate identifiers (ISIN, FIGI, provider-symbol) → asset."""

    __tablename__ = "asset_aliases"
    __table_args__ = (
        UniqueConstraint("kind", "value", name="uq_asset_aliases_kind_value"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # ticker, isin, figi, provider
    value: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)

    asset: Mapped[Asset] = relationship(back_populates="aliases")
