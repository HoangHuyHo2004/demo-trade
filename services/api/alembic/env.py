"""Alembic env — uses sync driver reading ALEMBIC_DATABASE_URL."""
from __future__ import annotations

import os
import pathlib

# make `app` importable
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Ensure importing app.db (which builds an async engine at import time) does
# not fail when only the sync Alembic URL is configured. If DATABASE_URL is
# unset, point it at an in-memory sqlite+aiosqlite URL so create_async_engine
# succeeds — Alembic itself will use ALEMBIC_DATABASE_URL below.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import app.models  # noqa: F401,E402  ensures all models registered
from app.db import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Env override
db_url = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("DATABASE_URL", "")
if db_url:
    # if user pointed at asyncpg, swap for sync psycopg
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
