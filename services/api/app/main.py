"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import (
    agent,
    assets,
    backtests,
    markets,
    portfolios,
    prices,
    providers,
    research,
    signals,
    watchlists,
)
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import (
    RateLimitMiddleware,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
)
from app.db import engine

settings = get_settings()
configure_logging(settings.log_level)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", app_env=settings.app_env, demo_mode=settings.demo_mode)
    yield
    await engine.dispose()
    log.info("shutdown")


app = FastAPI(
    title="DEMO-TRADE API",
    version="0.1.0",
    description="Investment research + trading-signal API (Phase 1 foundation).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Order: outermost first. Request ID must wrap security headers so it
# stamps every response, including 4xx from the limiter.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - start) * 1000
    log.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    return response


@app.get("/health", tags=["_ops"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["_ops"])
async def ready() -> JSONResponse:
    checks: dict[str, str] = {}
    ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:  # noqa: BLE001
        ok = False
        checks["database"] = f"error: {type(e).__name__}"
    return JSONResponse(
        {"status": "ready" if ok else "not_ready", "checks": checks},
        status_code=200 if ok else 503,
    )


app.include_router(assets.router, prefix="/api/v1/assets", tags=["assets"])
app.include_router(markets.router, prefix="/api/v1/markets", tags=["markets"])
app.include_router(prices.router, prefix="/api/v1/prices", tags=["prices"])
app.include_router(watchlists.router, prefix="/api/v1/watchlists", tags=["watchlists"])
app.include_router(providers.router, prefix="/api/v1/providers", tags=["providers"])
app.include_router(signals.router, prefix="/api/v1/signals", tags=["signals"])
app.include_router(backtests.router, prefix="/api/v1/backtests", tags=["backtests"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["agent"])
app.include_router(research.router, prefix="/api/v1/research", tags=["research"])
app.include_router(portfolios.router, prefix="/api/v1/portfolios", tags=["portfolios"])
