# Architecture

## Overview

DEMO-TRADE is a monorepo with three deployable services and two internal packages.

```
┌──────────┐   HTTPS/JSON   ┌────────────┐   asyncpg    ┌──────────┐
│ Next.js  │ ─────────────▶ │  FastAPI   │ ───────────▶ │ Postgres │
│  (web)   │                │   (api)    │              └──────────┘
└──────────┘                │            │
                            │            │              ┌──────────┐
                            │            │ ─── redis ──▶│  Redis   │
                            │            │              └──────────┘
                            └────┬───────┘                     ▲
                                 │                             │
                                 │                             │ celery
                                 ▼                             │
                          Provider registry           ┌──────────────┐
                          (mock in Phase 1)           │  Celery worker│
                                                      │   + beat      │
                                                      └──────────────┘
```

## Layers (Phase 1)

- **`apps/web`** — Next.js 15 App Router UI. Talks only to `api` via JSON.
  All financial displays show timestamp + source + market state.
- **`services/api`** — FastAPI application. Owns the DB, the provider
  registry, and the eventual signal engine. Every route uses Pydantic
  request/response models.
- **`services/worker`** — Celery worker + beat. Phase 1 runs a heartbeat and
  a stubbed quote-refresh job. Phase 2 fills in real ingest jobs.
- **`packages/contracts`** — Shared TypeScript types (asset id, quote,
  bar, watchlist, signal envelope). The API's Pydantic models are the
  source of truth; these mirror them.
- **`packages/config`** — Tiny runtime config helper reading `NEXT_PUBLIC_*`.

## Signal engine vs AI research agent

This separation is non-negotiable. See `AGENTS.md` §3. In Phase 1 neither
component is implemented; the routes and payload shapes are stubbed so
the frontend can render them without the models existing yet.

## Data model

Every table stores UTC timestamps. The `assets` table carries
`market_timezone` and `calendar`. `price_bars` has both an `event_time`
and an `available_at`, so back-testers can enforce no-lookahead.

See `alembic/versions/20260731_0001_init.py` for the concrete schema.

## Modes

- `DEMO_MODE=true` (default) → only the deterministic mock provider is
  registered; no external credentials are used or required.
- `DEMO_MODE=false` → real adapters will be selected based on which
  credentials are present. Phase 2 adds Alpaca, SSI FastConnect, and
  Coinbase public adapters.
