"""paper portfolios, transactions, snapshots (phase 5)

Revision ID: 20260804_0005
Revises: 20260803_0004
Create Date: 2026-08-04
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260804_0005"
down_revision = "20260803_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("base_currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "name", name="uq_portfolios_user_name"),
    )
    op.create_index("ix_portfolios_user_id", "portfolios", ["user_id"])

    op.create_table(
        "paper_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(),
                  sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer(),
                  sa.ForeignKey("assets.id", ondelete="RESTRICT"), nullable=True),
        # kind: BUY, SELL, DEPOSIT, WITHDRAW, DIVIDEND, FEE
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=False, server_default="0"),
        sa.Column("price", sa.Numeric(24, 10), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("fee", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index(
        "ix_paper_tx_portfolio_time",
        "paper_transactions", ["portfolio_id", "executed_at"],
    )
    op.create_index(
        "ix_paper_tx_asset", "paper_transactions", ["asset_id"],
    )

    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(),
                  sa.ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("base_currency", sa.String(8), nullable=False),
        sa.Column("cash_base", sa.Numeric(20, 6), nullable=False),
        sa.Column("equity_base", sa.Numeric(20, 6), nullable=False),
        sa.Column("positions_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.create_index(
        "ix_snapshots_portfolio_taken",
        "portfolio_snapshots", ["portfolio_id", "taken_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_snapshots_portfolio_taken", table_name="portfolio_snapshots")
    op.drop_table("portfolio_snapshots")
    op.drop_index("ix_paper_tx_asset", table_name="paper_transactions")
    op.drop_index("ix_paper_tx_portfolio_time", table_name="paper_transactions")
    op.drop_table("paper_transactions")
    op.drop_index("ix_portfolios_user_id", table_name="portfolios")
    op.drop_table("portfolios")
