# DEMO-TRADE

AI-assisted, multi-market investment **research and trading-signal** platform.
Supports US equities, Vietnamese equities (HOSE/HNX/UPCOM), and spot crypto.

> **Educational/research use only.** Not investment advice. No real-money order execution
> is implemented, and none is planned for the MVP. See `docs/compliance-considerations.md`.

---

## Status: **Phase 1 ✅** · **Phase 2 ✅** · **Phase 3 — Signal + backtest engines ✅**

Phase 1 (foundation):

- Monorepo layout (`apps/web`, `services/api`, `services/worker`, `packages/*`)
- Docker Compose local stack (Postgres + Redis + API + Worker + Web)
- Async FastAPI with structured logging, health/ready endpoints, versioned `/api/v1`
- SQLAlchemy 2.0 models + Alembic migrations
- **Canonical asset identity** (`{ASSET_TYPE}:{MARKET}:{EXCHANGE}:{SYMBOL}`) and
  ambiguity-safe symbol resolution
- **Deterministic mock market-data provider** (US equity, VN equity, crypto,
  per-market benchmarks) — no external credentials required
- Watchlist CRUD (demo user)
- Next.js 15 (App Router) + Tailwind + TanStack Query
- Dashboard, watchlist, asset detail with sparkline, i18n stubs (EN/VI)
- Mock auth, GitHub Actions CI, pytest suite

Phase 2 (this iteration — market data + charts):

- **Real Coinbase adapter** (public REST, no auth) — active out of the box
- **Alpaca adapter** (US equities) — auto-selects when `ALPACA_API_KEY/SECRET` set
- **SSI FastConnect adapter** (VN) — credential-gated skeleton, refuses without contract
- Registry with credential-based selection + rich `/api/v1/providers/status`
- **`BarRepository`** — DB-first bar reads with provider fallback, upserts on
  `(asset, interval, bar_time, source)`, audited via new `bar_ingest_runs` table
- Celery `refresh_bars` beat job for tracked assets
- **Interactive Lightweight Charts** on asset detail
- **Period selector** (1D · 1W · 1M · 3M · 6M · 1Y · 5Y · MAX) + per-period return badges
- **`/compare`** — multi-asset overlay (up to 5), rebased-to-100, currency-mismatch warning
- **Data-freshness badge** + provider-status panel on dashboard and asset detail
- US + VN holidays for 2025–2027; half-day sessions still deferred
- 29 pytest tests (added Coinbase mock-HTTP tests, bar-repository tests, calendar-holiday tests)

Phase 3 (this iteration — signal + backtest engines):

- Pure-function indicator library (SMA, EMA, MACD, RSI, ATR, realized vol,
  MDD, momentum, breakout, rvol z-score, relative strength) — fully unit-tested
- **`ensemble-v1`** rule-based signal model with trend / momentum / volatility /
  volume / benchmark factors; versioned `SignalModel` interface
- Signal engine with classification, heuristic confidence, ATR-based risk class,
  reference entry / invalidation / take-profit (only when defensible), full
  payload matching `packages/contracts/src/signals.ts`
- **Walk-forward backtester** with `available_at` no-lookahead guard (asserted
  in tests), per-market cost profiles, benchmarks (buy&hold, cash, SMA 50/200,
  market benchmark)
- API: `GET /signals/{id}`, `POST /signals/calculate`, `POST /backtests`,
  `GET /backtests/{id}`; persists `signals`, `signal_factors`, `backtest_runs`,
  `backtest_trades`, `backtest_equity_points`
- **Signal Laboratory** UI (`/lab/{id}`) with factor bar chart, parameter form,
  cost overrides, equity-curve chart, metrics vs baselines
- Methodology docs: `signal-methodology.md`, `backtesting-methodology.md`,
  `model-risk-management.md`
- 56 pytest tests total (indicators, engine, backtester, API smoke)

**Not yet implemented (deferred to later phases per spec §20):**

- AI research agent, filings/news retrieval, prompt-injection defenses (Phase 4)
- Paper portfolio, VaR, stress tests (Phase 5)
- Playwright E2E, full a11y sweep, production auth (Auth.js/OIDC)
- pgvector, object storage
- Half-day session calendars, SSI FastConnect OAuth flow, Alpaca WebSocket ingest

---

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Web:      http://localhost:3000
- API:      http://localhost:8000
- OpenAPI:  http://localhost:8000/docs
- Health:   http://localhost:8000/health

The `api` service runs Alembic migrations and seeds demo assets on startup
(idempotent). The stack works entirely in **demo mode** — no external API keys.

## Local dev without Docker

Backend:

```bash
cd services/api
python -m venv .venv && . .venv/Scripts/activate   # or source .venv/bin/activate
pip install -e .[dev]
export DATABASE_URL=postgresql+asyncpg://demotrade:demotrade@localhost:5432/demotrade
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app --reload
```

Frontend:

```bash
cd apps/web
pnpm install
pnpm dev
```

## Tests

```bash
# Python
cd services/api && pytest

# Web
cd apps/web && pnpm test
```

## Repository layout

```
apps/web              Next.js frontend
services/api          FastAPI backend (auth, providers, signals API surface)
services/worker       Celery worker + beat (ingest jobs)
packages/contracts    Shared TS types (asset id, signal payload shapes)
packages/config       Shared TS runtime config
infra                 Dockerfiles and infra manifests
docs                  Architecture, methodology, compliance docs
scripts               Repo-level utilities
tests                 Cross-service smoke tests
```

## Documents

- [`AGENTS.md`](AGENTS.md) — repo rules for AI collaborators & humans
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/data-providers.md`](docs/data-providers.md)
- [`docs/roadmap.md`](docs/roadmap.md)
- [`docs/compliance-considerations.md`](docs/compliance-considerations.md)
