"""jobs table for async work (phase 5.2 §14)

Revision ID: 20260801_0007
Revises: 20260801_0006
Create Date: 2026-08-01
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260801_0007"
down_revision = "20260801_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(48), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),   # backtest, research, portfolio_stress, ingest
        sa.Column("status", sa.String(24), nullable=False, server_default="QUEUED"),
        # status: QUEUED, COLLECTING_DATA, CALCULATING, GENERATING_REPORT, COMPLETE, FAILED
        sa.Column("progress", sa.Numeric(4, 3), nullable=False, server_default="0"),
        sa.Column("message", sa.String(500), nullable=False, server_default=""),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_public_id", "jobs", ["public_id"], unique=True)
    op.create_index("ix_jobs_user_status", "jobs", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_jobs_user_status", table_name="jobs")
    op.drop_index("ix_jobs_public_id", table_name="jobs")
    op.drop_table("jobs")
