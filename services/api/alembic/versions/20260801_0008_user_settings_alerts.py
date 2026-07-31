"""user_settings + alerts (spec §16)

Revision ID: 20260801_0008
Revises: 20260801_0007
Create Date: 2026-08-01
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260801_0008"
down_revision = "20260801_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        # UI-scope preferences that don't belong on `users`
        sa.Column("risk_display", sa.String(16), nullable=False, server_default="BOTH"),
        # BOTH | LEVEL_ONLY | SCORE_ONLY
        sa.Column("signal_horizon_default", sa.String(8), nullable=False, server_default="5D"),
        sa.Column("theme", sa.String(16), nullable=False, server_default="system"),
        sa.Column("notifications_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_user_settings_user_id", "user_settings", ["user_id"], unique=True)

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer(),
                  sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        # kind: PRICE_ABOVE, PRICE_BELOW, SIGNAL_CHANGES_TO
        sa.Column("threshold_numeric", sa.Numeric(24, 10), nullable=True),
        sa.Column("threshold_text", sa.String(32), nullable=True),  # e.g. "STRONG_BULLISH"
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        # ACTIVE, PAUSED, TRIGGERED, EXPIRED
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_alerts_user_status", "alerts", ["user_id", "status"])
    op.create_index("ix_alerts_asset", "alerts", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_alerts_asset", table_name="alerts")
    op.drop_index("ix_alerts_user_status", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_user_settings_user_id", table_name="user_settings")
    op.drop_table("user_settings")
