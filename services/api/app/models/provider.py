from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class ProviderStatus(Base, TimestampMixin):
    __tablename__ = "provider_status"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # market_data, fundamentals, ...
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")  # ok, degraded, down, unknown
    message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
