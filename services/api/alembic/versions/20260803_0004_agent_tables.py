"""agent runs, tool calls, audit logs, sources (phase 4)

Revision ID: 20260803_0004
Revises: 20260802_0003
Create Date: 2026-08-03
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260803_0004"
down_revision = "20260802_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("llm_provider", sa.String(32), nullable=False),
        sa.Column("llm_model", sa.String(64), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),  # ok, budget_exceeded, error, abstained
        sa.Column("tool_call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd_micro", sa.Integer(), nullable=False, server_default="0"),  # 1e-6 USD
        sa.Column("wallclock_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.String(1000), nullable=False, server_default=""),
        sa.Column("response_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_agent_runs_user_started", "agent_runs", ["user_id", "started_at"])
    op.create_index("ix_agent_runs_asset", "agent_runs", ["asset_id"])

    op.create_table(
        "tool_calls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(),
                  sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("tool", sa.String(64), nullable=False),
        sa.Column("args_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_summary", sa.String(2000), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("error_class", sa.String(64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_tool_calls_run_seq", "tool_calls", ["run_id", "seq"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(64), nullable=False),        # user, agent, worker, admin
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=True),
        sa.Column("subject_id", sa.String(64), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_audit_event_created", "audit_logs", ["event", "created_at"])

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),  # sec_filing, exchange_disclosure, news, project_post
        sa.Column("publisher", sa.String(128), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("asset_canonical_id", sa.String(96), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_sources_asset_pub", "sources", ["asset_canonical_id", "published_at"])
    op.create_index("ix_sources_body_hash", "sources", ["body_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sources_body_hash", table_name="sources")
    op.drop_index("ix_sources_asset_pub", table_name="sources")
    op.drop_table("sources")
    op.drop_index("ix_audit_event_created", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_tool_calls_run_seq", table_name="tool_calls")
    op.drop_table("tool_calls")
    op.drop_index("ix_agent_runs_asset", table_name="agent_runs")
    op.drop_index("ix_agent_runs_user_started", table_name="agent_runs")
    op.drop_table("agent_runs")
