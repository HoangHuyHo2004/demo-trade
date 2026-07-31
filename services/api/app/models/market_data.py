from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class Quote(Base, TimestampMixin):
    """Last-known quote per (asset, source). Written by providers/ingest jobs."""

    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("asset_id", "source", name="uq_quotes_asset_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # provider slug
    price: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingest_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PriceBar(Base, TimestampMixin):
    """OHLCV bar. Stores raw and adjusted-close distinctly."""

    __tablename__ = "price_bars"
    __table_args__ = (
        UniqueConstraint(
            "asset_id", "interval", "bar_time", "source",
            name="uq_price_bars_asset_interval_time_source",
        ),
        Index("ix_price_bars_asset_interval_time", "asset_id", "interval", "bar_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    interval: Mapped[str] = mapped_column(String(8), nullable=False)  # 1m,15m,1h,1d,1w,1mo
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    open: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 4), nullable=False, default=Decimal(0))

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    # audit
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingest_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        doc="When this bar became available to strategies (>= event_time; no lookahead).",
    )
