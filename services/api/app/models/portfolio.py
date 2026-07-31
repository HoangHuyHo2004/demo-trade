from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._mixins import TimestampMixin


class TxKind(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"
    DIVIDEND = "DIVIDEND"
    FEE = "FEE"


class Portfolio(Base, TimestampMixin):
    __tablename__ = "portfolios"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_portfolios_user_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")

    transactions: Mapped[list[PaperTransaction]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan",
        order_by="PaperTransaction.executed_at",
    )


class PaperTransaction(Base):
    __tablename__ = "paper_transactions"
    __table_args__ = (
        Index("ix_paper_tx_portfolio_time", "portfolio_id", "executed_at"),
        Index("ix_paper_tx_asset", "asset_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(28, 10), nullable=False, default=Decimal(0))
    price: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False, default=Decimal(0))
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal(0))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    portfolio: Mapped[Portfolio] = relationship(back_populates="transactions")


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (
        Index("ix_snapshots_portfolio_taken", "portfolio_id", "taken_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    cash_base: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    equity_base: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    positions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
