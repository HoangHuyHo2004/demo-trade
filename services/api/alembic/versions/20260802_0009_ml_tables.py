"""ML: users.is_admin + registry + training runs + datasets + predictions + outcomes

Revision ID: 20260802_0009
Revises: 20260801_0008
Create Date: 2026-08-02
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260802_0009"
down_revision = "20260801_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- 1. users.is_admin (spec: admin auth for train/promote/disable) ----
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))

    # ---- 2. ml_models: the model registry ----
    op.create_table(
        "ml_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(96), nullable=False, unique=True),
        # e.g. "us-equity-logreg-0.1.0" or "crypto-gbm-0.1.0"
        sa.Column("family", sa.String(32), nullable=False),   # logreg | ridge | rf | gbm | ensemble
        sa.Column("market", sa.String(16), nullable=False),   # US | VN | COINBASE
        sa.Column("horizon", sa.String(8), nullable=False),   # 1D | 5D | 20D
        sa.Column("task", sa.String(24), nullable=False),     # direction | regression | volatility | drawdown
        sa.Column("model_version", sa.String(48), nullable=False),
        sa.Column("dataset_version", sa.String(64), nullable=True),
        sa.Column("feature_version", sa.String(48), nullable=False),
        sa.Column("target_version", sa.String(48), nullable=False),
        # State machine (spec):
        #   EXPERIMENTAL, VALIDATED, SHADOW, CHAMPION, CHALLENGER,
        #   DEGRADED, DISABLED, RETIRED
        sa.Column("state", sa.String(24), nullable=False, server_default="EXPERIMENTAL"),
        sa.Column("params_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("artifact_path", sa.String(500), nullable=True),
        sa.Column("artifact_sha256", sa.String(64), nullable=True),
        sa.Column("code_commit", sa.String(40), nullable=True),
        sa.Column("dep_versions_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_by_user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approval_note", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ml_models_code", "ml_models", ["code"], unique=True)
    op.create_index("ix_ml_models_market_state", "ml_models", ["market", "state"])

    # ---- 3. ml_datasets: reproducible training-data snapshots ----
    op.create_table(
        "ml_datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dataset_version", sa.String(64), nullable=False, unique=True),
        sa.Column("market", sa.String(16), nullable=False),
        sa.Column("universe_version", sa.String(48), nullable=False),
        sa.Column("feature_version", sa.String(48), nullable=False),
        sa.Column("target_version", sa.String(48), nullable=False),
        sa.Column("from_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("to_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("notes", sa.String(500), nullable=False, server_default=""),
    )
    op.create_index("ix_ml_datasets_market_created", "ml_datasets", ["market", "created_at"])

    # ---- 4. ml_training_runs: every training attempt ----
    op.create_table(
        "ml_training_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(48), nullable=False, unique=True),
        sa.Column("model_id", sa.Integer(),
                  sa.ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", sa.Integer(),
                  sa.ForeignKey("ml_datasets.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("seed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("train_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("train_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("val_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("val_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("test_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("test_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("calibration_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("code_commit", sa.String(40), nullable=True),
        sa.Column("dep_versions_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("artifact_sha256", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="QUEUED"),
        # QUEUED, LOADING_DATA, FITTING, CALIBRATING, EVALUATING, COMPLETE, FAILED
        sa.Column("message", sa.String(1000), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_ml_training_runs_model_created",
                     "ml_training_runs", ["model_id", "created_at"])

    # ---- 5. ml_predictions: saved BEFORE the outcome is known (spec §20 no-rewrite) ----
    op.create_table(
        "ml_predictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_id", sa.Integer(),
                  sa.ForeignKey("ml_models.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("asset_id", sa.Integer(),
                  sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon", sa.String(8), nullable=False),
        sa.Column("model_version", sa.String(48), nullable=False),
        sa.Column("data_version", sa.String(64), nullable=False),
        # Direction / probability
        sa.Column("prob_positive", sa.Numeric(5, 4), nullable=True),
        sa.Column("prob_negative", sa.Numeric(5, 4), nullable=True),
        # Regression
        sa.Column("expected_return_median", sa.Numeric(10, 6), nullable=True),
        sa.Column("expected_return_lower", sa.Numeric(10, 6), nullable=True),
        sa.Column("expected_return_upper", sa.Numeric(10, 6), nullable=True),
        sa.Column("expected_volatility", sa.Numeric(10, 6), nullable=True),
        # Ancillary
        sa.Column("trend_continuation_prob", sa.Numeric(5, 4), nullable=True),
        sa.Column("drawdown_risk", sa.String(16), nullable=True),   # LOW/MEDIUM/HIGH
        sa.Column("market_regime", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("ood_score", sa.Numeric(6, 4), nullable=True),
        sa.Column("positive_contributors_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("negative_contributors_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_ml_predictions_asset_asof", "ml_predictions", ["asset_id", "as_of"])
    op.create_index("ix_ml_predictions_model_asof", "ml_predictions", ["model_id", "as_of"])

    # ---- 6. ml_prediction_outcomes: honest post-hoc scoring ----
    op.create_table(
        "ml_prediction_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prediction_id", sa.Integer(),
                  sa.ForeignKey("ml_predictions.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("actual_return", sa.Numeric(10, 6), nullable=True),
        sa.Column("actual_direction", sa.SmallInteger(), nullable=True),  # -1, 0, 1
        sa.Column("max_favorable", sa.Numeric(10, 6), nullable=True),
        sa.Column("max_adverse", sa.Numeric(10, 6), nullable=True),
        sa.Column("was_correct", sa.Boolean(), nullable=True),
        sa.Column("calibration_bucket", sa.String(16), nullable=True),  # e.g. "0.60-0.70"
        sa.Column("strategy_pnl_after_costs", sa.Numeric(10, 6), nullable=True),
        sa.Column("market_regime", sa.String(32), nullable=True),
        sa.Column("data_was_corrected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ml_prediction_outcomes")
    op.drop_index("ix_ml_predictions_model_asof", table_name="ml_predictions")
    op.drop_index("ix_ml_predictions_asset_asof", table_name="ml_predictions")
    op.drop_table("ml_predictions")
    op.drop_index("ix_ml_training_runs_model_created", table_name="ml_training_runs")
    op.drop_table("ml_training_runs")
    op.drop_index("ix_ml_datasets_market_created", table_name="ml_datasets")
    op.drop_table("ml_datasets")
    op.drop_index("ix_ml_models_market_state", table_name="ml_models")
    op.drop_index("ix_ml_models_code", table_name="ml_models")
    op.drop_table("ml_models")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_admin")
