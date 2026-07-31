"""users: oauth_provider + oauth_account_id (phase 5.1 auth)

Revision ID: 20260801_0006
Revises: 20260804_0005
Create Date: 2026-08-01
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260801_0006"
down_revision = "20260804_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("oauth_provider", sa.String(32), nullable=True))
        batch.add_column(sa.Column("oauth_account_id", sa.String(128), nullable=True))
    op.create_index(
        "uq_users_oauth_identity",
        "users",
        ["oauth_provider", "oauth_account_id"],
        unique=True,
        postgresql_where=sa.text("oauth_provider IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_oauth_identity", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("oauth_account_id")
        batch.drop_column("oauth_provider")
