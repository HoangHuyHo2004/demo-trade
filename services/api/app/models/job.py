from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    COLLECTING_DATA = "COLLECTING_DATA"
    CALCULATING = "CALCULATING"
    GENERATING_REPORT = "GENERATING_REPORT"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class JobKind(StrEnum):
    BACKTEST = "backtest"
    RESEARCH = "research"
    PORTFOLIO_STRESS = "portfolio_stress"
    INGEST = "ingest"


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_public_id", "public_id", unique=True),
        Index("ix_jobs_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(48), nullable=False, unique=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=JobStatus.QUEUED.value
    )
    progress: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, default=Decimal(0))
    message: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
