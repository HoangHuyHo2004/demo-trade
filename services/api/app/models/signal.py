from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._mixins import TimestampMixin


class SignalModelVersion(Base):
    __tablename__ = "signal_model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    family: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signals_asset_horizon_asof", "asset_id", "horizon", "as_of"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    model_version_id: Mapped[int] = mapped_column(
        ForeignKey("signal_model_versions.id", ondelete="RESTRICT"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon: Mapped[str] = mapped_column(String(8), nullable=False)
    classification: Mapped[str] = mapped_column(String(24), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    risk: Mapped[str] = mapped_column(String(16), nullable=False)
    data_quality: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    regime: Mapped[str] = mapped_column(String(24), nullable=False)
    data_version: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    factors: Mapped[list[SignalFactor]] = relationship(
        back_populates="signal", cascade="all, delete-orphan"
    )
    model_version: Mapped[SignalModelVersion] = relationship(lazy="joined")


class SignalFactor(Base):
    __tablename__ = "signal_factors"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    contribution: Mapped[Decimal] = mapped_column(Numeric(5, 3), nullable=False)
    detail: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    signal: Mapped[Signal] = relationship(back_populates="factors")


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_runs_asset_created", "asset_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    model_version_id: Mapped[int] = mapped_column(
        ForeignKey("signal_model_versions.id", ondelete="RESTRICT"), nullable=False
    )
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cost_bps: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    slippage_bps: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    horizon: Mapped[str] = mapped_column(String(8), nullable=False)
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    trades: Mapped[list[BacktestTrade]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    equity: Mapped[list[BacktestEquityPoint]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    bars_held: Mapped[int] = mapped_column(nullable=False)
    pnl_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    cost_pct: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    run: Mapped[BacktestRun] = relationship(back_populates="trades")


class BacktestEquityPoint(Base):
    __tablename__ = "backtest_equity_points"
    __table_args__ = (
        Index("ix_backtest_equity_run_bar", "run_id", "bar_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False
    )
    bar_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    strategy_equity: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    buy_hold_equity: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    in_position: Mapped[bool] = mapped_column(nullable=False, default=False)

    run: Mapped[BacktestRun] = relationship(back_populates="equity")


# Silence "unused mixin" ruff warnings — TimestampMixin isn't used here on
# purpose; signal/backtest rows are immutable append-only records.
_ = TimestampMixin
