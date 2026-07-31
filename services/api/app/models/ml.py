from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class MLModelState(StrEnum):
    EXPERIMENTAL = "EXPERIMENTAL"
    VALIDATED = "VALIDATED"
    SHADOW = "SHADOW"
    CHAMPION = "CHAMPION"
    CHALLENGER = "CHALLENGER"
    DEGRADED = "DEGRADED"
    DISABLED = "DISABLED"
    RETIRED = "RETIRED"


class MLTask(StrEnum):
    DIRECTION = "direction"
    REGRESSION = "regression"
    VOLATILITY = "volatility"
    DRAWDOWN = "drawdown"


class MLFamily(StrEnum):
    LOGREG = "logreg"
    RIDGE = "ridge"
    RF = "rf"
    GBM = "gbm"
    ENSEMBLE = "ensemble"


class MLTrainingStatus(StrEnum):
    QUEUED = "QUEUED"
    LOADING_DATA = "LOADING_DATA"
    FITTING = "FITTING"
    CALIBRATING = "CALIBRATING"
    EVALUATING = "EVALUATING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class MLModel(Base):
    __tablename__ = "ml_models"
    __table_args__ = (
        Index("ix_ml_models_code", "code", unique=True),
        Index("ix_ml_models_market_state", "market", "state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)
    family: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False)
    horizon: Mapped[str] = mapped_column(String(8), nullable=False)
    task: Mapped[str] = mapped_column(String(24), nullable=False)
    model_version: Mapped[str] = mapped_column(String(48), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    feature_version: Mapped[str] = mapped_column(String(48), nullable=False)
    target_version: Mapped[str] = mapped_column(String(48), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, default=MLModelState.EXPERIMENTAL.value)
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    artifact_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code_commit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    dep_versions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approval_note: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    training_runs: Mapped[list[MLTrainingRun]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )


class MLDataset(Base):
    __tablename__ = "ml_datasets"
    __table_args__ = (
        Index("ix_ml_datasets_market_created", "market", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_version: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False)
    universe_version: Mapped[str] = mapped_column(String(48), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(48), nullable=False)
    target_version: Mapped[str] = mapped_column(String(48), nullable=False)
    from_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    to_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")


class MLTrainingRun(Base):
    __tablename__ = "ml_training_runs"
    __table_args__ = (
        Index("ix_ml_training_runs_model_created", "model_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[int | None] = mapped_column(
        ForeignKey("ml_datasets.id", ondelete="RESTRICT"), nullable=True
    )
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    train_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    train_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    val_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    val_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    test_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    test_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    calibration_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    code_commit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    dep_versions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=MLTrainingStatus.QUEUED.value)
    message: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    model: Mapped[MLModel] = relationship(back_populates="training_runs")


class MLPrediction(Base):
    __tablename__ = "ml_predictions"
    __table_args__ = (
        Index("ix_ml_predictions_asset_asof", "asset_id", "as_of"),
        Index("ix_ml_predictions_model_asof", "model_id", "as_of"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("ml_models.id", ondelete="RESTRICT"), nullable=False
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    horizon: Mapped[str] = mapped_column(String(8), nullable=False)
    model_version: Mapped[str] = mapped_column(String(48), nullable=False)
    data_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prob_positive: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    prob_negative: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    expected_return_median: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    expected_return_lower: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    expected_return_upper: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    expected_volatility: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    trend_continuation_prob: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    drawdown_risk: Mapped[str | None] = mapped_column(String(16), nullable=True)
    market_regime: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    ood_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    positive_contributors_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    negative_contributors_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MLPredictionOutcome(Base):
    __tablename__ = "ml_prediction_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("ml_predictions.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    actual_return: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    actual_direction: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    max_favorable: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    max_adverse: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    was_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    calibration_bucket: Mapped[str | None] = mapped_column(String(16), nullable=True)
    strategy_pnl_after_costs: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    market_regime: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_was_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
