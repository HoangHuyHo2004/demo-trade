"""initial schema (phase 1)

Revision ID: 20260731_0001
Revises:
Create Date: 2026-07-31
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260731_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("locale", sa.String(8), nullable=False, server_default="en"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "exchanges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("market", sa.String(16), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("calendar", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_exchanges_code", "exchanges", ["code"], unique=True)

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_id", sa.String(96), nullable=False, unique=True),
        sa.Column("asset_type", sa.String(16), nullable=False),
        sa.Column("market", sa.String(16), nullable=False),
        sa.Column("exchange_code", sa.String(16), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("display_symbol", sa.String(32), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("quote_currency", sa.String(8), nullable=False),
        sa.Column("base_asset", sa.String(16), nullable=True),
        sa.Column("quote_asset", sa.String(16), nullable=True),
        sa.Column("market_timezone", sa.String(64), nullable=False),
        sa.Column("calendar", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_benchmark", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_assets_canonical_id", "assets", ["canonical_id"], unique=True)
    op.create_index("ix_assets_market", "assets", ["market"])
    op.create_index("ix_assets_exchange_code", "assets", ["exchange_code"])
    op.create_index("ix_assets_symbol", "assets", ["symbol"])

    op.create_table(
        "asset_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("value", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("kind", "value", name="uq_asset_aliases_kind_value"),
    )
    op.create_index("ix_asset_aliases_asset_id", "asset_aliases", ["asset_id"])
    op.create_index("ix_asset_aliases_value", "asset_aliases", ["value"])

    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),
    )
    op.create_index("ix_watchlists_user_id", "watchlists", ["user_id"])

    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("watchlist_id", sa.Integer(), sa.ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("watchlist_id", "asset_id", name="uq_watchlist_items_wl_asset"),
    )
    op.create_index("ix_watchlist_items_watchlist_id", "watchlist_items", ["watchlist_id"])
    op.create_index("ix_watchlist_items_asset_id", "watchlist_items", ["asset_id"])

    op.create_table(
        "quotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("price", sa.Numeric(24, 10), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingest_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("asset_id", "source", name="uq_quotes_asset_source"),
    )
    op.create_index("ix_quotes_asset_id", "quotes", ["asset_id"])

    op.create_table(
        "price_bars",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interval", sa.String(8), nullable=False),
        sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(24, 10), nullable=False),
        sa.Column("high", sa.Numeric(24, 10), nullable=False),
        sa.Column("low", sa.Numeric(24, 10), nullable=False),
        sa.Column("close", sa.Numeric(24, 10), nullable=False),
        sa.Column("adj_close", sa.Numeric(24, 10), nullable=True),
        sa.Column("volume", sa.Numeric(28, 4), nullable=False, server_default="0"),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingest_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "asset_id", "interval", "bar_time", "source",
            name="uq_price_bars_asset_interval_time_source",
        ),
    )
    op.create_index(
        "ix_price_bars_asset_interval_time",
        "price_bars",
        ["asset_id", "interval", "bar_time"],
    )

    op.create_table(
        "provider_status",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False, unique=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("message", sa.String(500), nullable=False, server_default=""),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_provider_status_provider", "provider_status", ["provider"], unique=True)


def downgrade() -> None:
    op.drop_table("provider_status")
    op.drop_table("price_bars")
    op.drop_table("quotes")
    op.drop_table("watchlist_items")
    op.drop_table("watchlists")
    op.drop_table("asset_aliases")
    op.drop_table("assets")
    op.drop_table("exchanges")
    op.drop_table("users")
