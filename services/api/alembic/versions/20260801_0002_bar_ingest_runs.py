"""bar ingest run audit table

Revision ID: 20260801_0002
Revises: 20260731_0001
Create Date: 2026-08-01
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260801_0002"
down_revision = "20260731_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bar_ingest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(),
                  sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("interval", sa.String(8), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bars_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bars_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("message", sa.String(500), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_bar_ingest_runs_asset_interval_started",
        "bar_ingest_runs",
        ["asset_id", "interval", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_bar_ingest_runs_asset_interval_started", table_name="bar_ingest_runs")
    op.drop_table("bar_ingest_runs")
