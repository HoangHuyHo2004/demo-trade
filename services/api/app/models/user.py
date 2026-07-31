from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models._mixins import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    oauth_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    oauth_account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_admin: Mapped[bool] = mapped_column(nullable=False, default=False)
