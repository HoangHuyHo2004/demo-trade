from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class Exchange(Base, TimestampMixin):
    """Exchanges + their trading calendar identifiers.

    ``calendar`` names a rule set consumed by the market-status service. In
    Phase 1 we implement calendars for XNYS (US), XHOS/XHNX/UPCOM (VN), and
    24/7 crypto. Half-day handling is deferred to Phase 2.
    """

    __tablename__ = "exchanges"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False)  # US, VN, COINBASE, ...
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    calendar: Mapped[str] = mapped_column(String(32), nullable=False)
