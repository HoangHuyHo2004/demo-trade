"""signals + backtests tables (phase 3)

Revision ID: 20260802_0003
Revises: 20260801_0002
Create Date: 2026-08-02
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260802_0003"
down_revision = "20260801_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_model_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("family", sa.String(32), nullable=False),  # ensemble, ml, ...
        sa.Column("description", sa.String(1000), nullable=False, server_default=""),
        sa.Column("params_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_signal_model_versions_code", "signal_model_versions", ["code"], unique=True)

    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(),
                  sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_version_id", sa.Integer(),
                  sa.ForeignKey("signal_model_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon", sa.String(8), nullable=False),  # 1D, 5D, 20D
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("score", sa.Numeric(6, 2), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("risk", sa.String(16), nullable=False),
        sa.Column("data_quality", sa.Numeric(4, 3), nullable=False),
        sa.Column("regime", sa.String(24), nullable=False),
        sa.Column("data_version", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index(
        "ix_signals_asset_horizon_asof",
        "signals",
        ["asset_id", "horizon", "as_of"],
    )

    op.create_table(
        "signal_factors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("signal_id", sa.Integer(),
                  sa.ForeignKey("signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(48), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),  # trend, momentum, volatility, volume, ...
        sa.Column("contribution", sa.Numeric(5, 3), nullable=False),  # -1..1
        sa.Column("detail", sa.String(500), nullable=False, server_default=""),
    )
    op.create_index("ix_signal_factors_signal_id", "signal_factors", ["signal_id"])

    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(),
                  sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_version_id", sa.Integer(),
                  sa.ForeignKey("signal_model_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("interval", sa.String(8), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cost_bps", sa.Numeric(6, 2), nullable=False),
        sa.Column("slippage_bps", sa.Numeric(6, 2), nullable=False),
        sa.Column("horizon", sa.String(8), nullable=False),
        sa.Column("params_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("message", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_backtest_runs_asset_created", "backtest_runs", ["asset_id", "created_at"])

    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(),
                  sa.ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),  # long, short (Phase 3: long only)
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Numeric(24, 10), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_price", sa.Numeric(24, 10), nullable=False),
        sa.Column("bars_held", sa.Integer(), nullable=False),
        sa.Column("pnl_pct", sa.Numeric(10, 6), nullable=False),
        sa.Column("cost_pct", sa.Numeric(8, 6), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False, server_default=""),
    )
    op.create_index("ix_backtest_trades_run_id", "backtest_trades", ["run_id"])

    op.create_table(
        "backtest_equity_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(),
                  sa.ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("strategy_equity", sa.Numeric(20, 10), nullable=False),
        sa.Column("buy_hold_equity", sa.Numeric(20, 10), nullable=False),
        sa.Column("in_position", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_backtest_equity_run_bar",
        "backtest_equity_points",
        ["run_id", "bar_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_equity_run_bar", table_name="backtest_equity_points")
    op.drop_table("backtest_equity_points")
    op.drop_index("ix_backtest_trades_run_id", table_name="backtest_trades")
    op.drop_table("backtest_trades")
    op.drop_index("ix_backtest_runs_asset_created", table_name="backtest_runs")
    op.drop_table("backtest_runs")
    op.drop_index("ix_signal_factors_signal_id", table_name="signal_factors")
    op.drop_table("signal_factors")
    op.drop_index("ix_signals_asset_horizon_asof", table_name="signals")
    op.drop_table("signals")
    op.drop_index("ix_signal_model_versions_code", table_name="signal_model_versions")
    op.drop_table("signal_model_versions")
