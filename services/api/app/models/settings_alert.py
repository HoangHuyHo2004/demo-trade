from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RiskDisplay(StrEnum):
    BOTH = "BOTH"
    LEVEL_ONLY = "LEVEL_ONLY"
    SCORE_ONLY = "SCORE_ONLY"


class AlertKind(StrEnum):
    PRICE_ABOVE = "PRICE_ABOVE"
    PRICE_BELOW = "PRICE_BELOW"
    SIGNAL_CHANGES_TO = "SIGNAL_CHANGES_TO"


class AlertStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    TRIGGERED = "TRIGGERED"
    EXPIRED = "EXPIRED"


class UserSettings(Base):
    __tablename__ = "user_settings"
    __table_args__ = (
        Index("ix_user_settings_user_id", "user_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    risk_display: Mapped[str] = mapped_column(String(16), nullable=False,
                                              default=RiskDisplay.BOTH.value)
    signal_horizon_default: Mapped[str] = mapped_column(String(8), nullable=False,
                                                         default="5D")
    theme: Mapped[str] = mapped_column(String(16), nullable=False, default="system")
    notifications_email: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                                       default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_user_status", "user_id", "status"),
        Index("ix_alerts_asset", "asset_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold_numeric: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    threshold_text: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=AlertStatus.ACTIVE.value)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
