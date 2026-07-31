"""Test config: force sqlite+aiosqlite engine before app imports."""
from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["ALEMBIC_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DEMO_MODE"] = "true"
os.environ["API_SECRET_KEY"] = "test-secret-key-longer-than-thirty-two-chars-abc"
os.environ["USE_MOCK_PROVIDERS_ONLY"] = "true"
# Force in-memory rate limiter (no Redis reachable in tests)
os.environ["REDIS_URL"] = ""
# Backtest jobs run inline in the request thread (no Celery in tests)
os.environ["USE_SYNC_JOBS"] = "true"

import asyncio  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401,E402  register models

# Import AFTER env vars are set so settings pick up the sqlite URL.
from app import db as db_module  # noqa: E402
from app.db import Base  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture()
async def engine():
    # Fresh in-memory DB per test.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Swap module engine so app code shares it.
    orig_engine = db_module.engine
    orig_factory = db_module.SessionLocal
    db_module.engine = engine
    db_module.SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    yield engine
    db_module.engine = orig_engine
    db_module.SessionLocal = orig_factory
    await engine.dispose()


@pytest_asyncio.fixture()
async def session(engine) -> AsyncIterator[AsyncSession]:
    async with db_module.SessionLocal() as s:
        yield s


@pytest_asyncio.fixture()
async def client(engine) -> AsyncIterator[AsyncClient]:
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
