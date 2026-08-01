# DEMO-TRADE

AI-assisted, multi-market investment **research and trading-signal** platform.
Supports US equities, Vietnamese equities (HOSE/HNX/UPCOM), and spot crypto.

> **Educational/research use only.** Not investment advice. No real-money order execution
> is implemented, and none is planned for the MVP. See `docs/compliance-considerations.md`.

---

## Status: **Phase 1 ✅** · **Phase 2 ✅** · **Phase 3 ✅** · **Phase 4 ✅** · **Phase 5 ✅** · **Phase 5.1 ✅** · **Phase 5.2 ✅** · **ML Phase 1 — Baseline models (shadow-only) ✅**

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

Phase 4 (this iteration — AI research agent):

- Pluggable LLM abstraction — `MockLLMProvider` (deterministic; demo & CI
  default) + `AnthropicProvider` (real Claude Sonnet 5; credential-gated)
- Typed tool allowlist with strict Pydantic schemas (`extra="forbid"`):
  resolve, market status, quote, historical bars, calculated indicators,
  signal, backtest, compare
- Search-tool skeletons (SEC / VN disclosures / IR announcements / crypto
  project posts / curated news) — return `status="not_available"` so the
  agent abstains honestly rather than fabricating a citation
- Orchestrator with per-turn budgets (max tool calls / tokens / wall-clock /
  cost), delimited `<untrusted_source>` wrapping of every tool result,
  full audit trail (`agent_runs`, `tool_calls`, `audit_logs`, `sources`)
- Structured `ResearchResponse` separating facts / interpretation /
  assumptions / unknowns with a citations panel; abstains cleanly when
  data missing or LLM output isn't valid JSON
- Signal-engine boundary: agent can request a signal but never invent
  one — enforced in code + asserted by tests
- API: `POST /agent/chat`, `GET /agent/runs/{id}`, `GET /research/{id}`
- Web: `/research` chat page + `ResearchResponseView` component + link
  from asset detail
- `docs/agent-security.md` — threat model, allowlist, defenses, budgets,
  audit, residual risks
- 73 pytest tests total (added 17 agent tests covering schema validation,
  injection resistance, budget enforcement, audit-trail redaction,
  signal-engine boundary)

Phase 5 (this iteration — paper portfolio + production hardening):

- **Paper portfolio** with manual transactions (BUY/SELL/DEPOSIT/WITHDRAW/
  DIVIDEND/FEE); WAC cost basis; realized + unrealized P&L; per-currency
  cash + base-currency valuation via FX service
- **FX service** — dated fixed-rate table for demo (USD/VND/EUR); same
  interface flips into a live provider later without touching business code
- **Risk analytics** — allocation by asset & market, HHI concentration,
  historical vol + max drawdown, historical VaR 95%/99%, correlation
  matrix, stress scenarios (−5/−10/−20/−30% risk-asset shock)
- **Security headers middleware** — CSP, X-Frame-Options, Referrer-Policy,
  Permissions-Policy, cross-origin isolation, HSTS in production
- **Request-ID middleware** — binds into structured-log context; echoes
  `X-Request-Id`
- **Rate limiter** — Redis-backed with in-memory fallback; per-rule
  buckets; auto-disables Redis after first failure so demo installs
  don't hang
- **Audit-log rows** on portfolio mutations (create, add transaction)
- **Web `/portfolio` page** — portfolio picker, overview stats, positions
  table with per-position P&L, transaction form, risk widget with
  allocation bars and stress scenarios
- **`docs/deployment.md`** + **`docs/operations-runbook.md`**
- 89 pytest tests total (added 16 tests covering FX conversion, WAC
  math, cash flow accounting, valuation end-to-end, security headers,
  request-ID, in-memory rate limiter, end-to-end rate-limit trip)

Phase 5.1 (this iteration — production auth):

- **Auth.js v5** in the web app with GitHub OIDC + demo-credentials
  providers. Session cookie is an **HS256-signed JWT** using a shared
  `AUTH_SECRET`, so FastAPI verifies it with PyJWT — no round-trip.
- Migration 0006: `users.oauth_provider` + `users.oauth_account_id`
  with a partial unique index; users are upserted by (provider, subject)
  on first login.
- `app/core/auth.py`: session issuer + verifier with strict claim
  requirements (exp, sub) and a maximum-TTL safety cap so a leaked
  secret can't mint infinite-lived tokens.
- Updated `deps.get_current_user`: cookie or Bearer JWT first, demo
  auto-provision fallback only when `DEMO_MODE=true`; explicit bad
  cookies still 401 (fail closed).
- New endpoints: `GET /api/v1/auth/me`, `POST /api/v1/auth/demo-login`
  (demo-mode only), `POST /api/v1/auth/logout`.
- Web: `/signin` server page + `AuthButton` in top nav + middleware
  that redirects unauthenticated users (auth handlers + static allowed).
- Docker Compose plumbs the shared secret into both containers.
- 99 pytest tests total (added 10 auth tests: JWT roundtrip, wrong
  secret, expired, missing exp, too-far-future TTL, /me demo-off,
  demo-login flow, Bearer header, invalid cookie 401, logout clears)

Phase 5.2 (this iteration — spec gap-fill):

- **Per-market signal weights** (US / VN / crypto profiles) —
  spec §8 no longer uses one weight table for every market
- **Signal payload additive fields** (spec §9): `data_source`,
  `data_freshness`, `model_version`, `expected_holding_period`,
  combined `warnings`. Historical field names remain as aliases so
  the current UI keeps rendering.
- **API surface aliases** (spec §10):
  `/api/v1/assets/{id}/quote|bars|signal` delegate to the existing
  handlers; `/watchlists/{id}/assets` alias.
- **`POST /api/v1/assets/compare`** — backend counterpart of the web
  compare page (up to 5 assets, aligned closes rebased to 100).
- **Async job pattern** (spec §14): `jobs` table, `POST /backtests`
  returns 202 + `{job_id}`, `GET /jobs/{id}` polls. Celery task runs
  the same inline runner as the sync path. `USE_SYNC_JOBS=true`
  (default in tests + Redis-less demo installs) runs the job inline.
- **`user_settings` + `alerts` entities** (spec §16). Settings API
  + `/settings` web page (language, currency, timezone, default
  signal horizon, risk display, theme, email notifications). Alerts
  table present for the scheduler; no UI yet.
- **Playwright** critical-flow E2E (`pnpm --filter web e2e`).
- New docs: `docs/assumptions.md`, `docs/local-development.md`,
  `docs/api.md`, `docs/security.md`, `docs/ai-agent.md`.
- **109 pytest tests total** (added 10 new: jobs lifecycle + inline
  runner + endpoint round-trip + settings CRUD).

ML Phase 1 (this iteration — baseline models, shadow-only):

- **New service `services/ml_worker`** — separate Celery app carrying
  scikit-learn/joblib/pandas so the low-latency `api` service stays
  free of ~150MB of ML deps. Shares the api's pure-Python pipeline
  code (`app/ml/*`) via `PYTHONPATH`.
- **Point-in-time feature pipeline** (`app/ml/features.py`) — 28
  features (returns, trend, momentum, volatility, volume, benchmark-
  relative), every one a pure function of a truncated bar prefix, so
  lookahead is structurally impossible rather than policy-enforced.
- **Cost-adjusted labels** (`app/ml/labels.py`) — direction (with a
  neutral zone that widens with assumed transaction cost), future
  return, future volatility, future max drawdown.
- **Deterministic dataset builder** (`app/ml/datasets.py`) —
  `available_at`-gated bar loading, versioned `dataset_version` hash,
  walk-forward fold generator (expanding train / rolling validation /
  embargo gap).
- **Baseline models**: `logreg`, `rf`, `gbm` — trained, validated per
  fold, probability-calibrated (isotonic/sigmoid on the validation
  fold, never the test set), persisted with a sha256-checked artifact.
- **Model registry** (`ml_models` table) with an
  EXPERIMENTAL→SHADOW→CHAMPION/CHALLENGER/DISABLED state machine.
  **Only `SHADOW`/`CHAMPION` models generate predictions, and no ML
  prediction is ever merged into the rule-based `Signal` in Phase 1**
  — they're served from a completely separate table and endpoint.
- API: `GET/POST /api/v1/ml/*` (reads open to any signed-in user;
  train/promote/disable require `users.is_admin`, seeded true for the
  demo user in `DEMO_MODE`).
- Web: `MLPredictionCard` on asset detail, permanently labeled
  `SHADOW · does not influence signal`.
- **11 required ML docs** written accurately against what's actually
  built, not aspirationally — see `docs/ml-limitations.md` first.
- **143 api pytest tests total** (+34 for the ML pipeline: feature
  determinism, label no-lookahead, dataset point-in-time correctness,
  walk-forward fold structure, API admin-gating).
- **12 ml_worker pytest tests** run against real scikit-learn on
  synthetic data with a genuine signal (not just import checks) —
  caught and fixed two real bugs in the process: an undefined-variable
  crash in the contribution-generation code, and a scikit-learn 1.6+
  breaking change (`CalibratedClassifierCV(cv="prefit")` removal,
  fixed with a version-compatible `FrozenEstimator` fallback).

**Not yet implemented:**

- SEC/VN filings retrieval + `pgvector` RAG (Phase 4.1)
- OpenTelemetry traces + Prometheus metrics endpoint
- Runtime-configurable rate-limit rules
- Tax-lot cost accounting (FIFO/LIFO/specific-lot)
- Half-day session calendars, SSI FastConnect OAuth flow, Alpaca WebSocket ingest
- ML ensemble integration, out-of-distribution detection, drift
  monitoring, champion/challenger comparison, agent ML explanation
  tool, model-performance dashboard (all explicitly later ML phases
  per spec — see `docs/roadmap.md`)

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

ML worker (optional — only needed to exercise `POST /api/v1/ml/train`):

```bash
cd services/ml_worker
python -m venv .venv && . .venv/Scripts/activate
pip install -e .[dev]
export PYTHONPATH=../api:.
export DATABASE_URL=postgresql+asyncpg://demotrade:demotrade@localhost:5432/demotrade
# Dedicated DB indices — different from the market-data `worker`
# service's (1, 2), otherwise both Celery apps misroute each other's
# tasks over the same broker namespace. The api service must set the
# same CELERY_BROKER_URL/CELERY_RESULT_BACKEND for POST /ml/train to
# actually reach this worker (see docker-compose.yml for the wiring).
export CELERY_BROKER_URL=redis://localhost:6379/3
export CELERY_RESULT_BACKEND=redis://localhost:6379/4
celery -A mlw.celery_app:app worker -B --loglevel=INFO
```

## Tests

```bash
# API (includes ML pipeline tests — no sklearn needed, pure functions only)
cd services/api && pytest

# ML worker (requires scikit-learn — separate venv, see above)
cd services/ml_worker && pytest

# Web
cd apps/web && pnpm test
```

## Repository layout

```
apps/web              Next.js frontend
services/api          FastAPI backend (auth, providers, signals, ML pipeline)
services/worker       Celery worker + beat (market-data ingest jobs)
services/ml_worker     Celery worker for ML training/inference (scikit-learn)
packages/contracts    Shared TS types (asset id, signal payload shapes)
packages/config       Shared TS runtime config
infra                 Dockerfiles and infra manifests
docs                  Architecture, methodology, compliance, ML docs
scripts               Repo-level utilities
tests                 Cross-service smoke tests
```

## Documents

- [`AGENTS.md`](AGENTS.md) — repo rules for AI collaborators & humans
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/data-providers.md`](docs/data-providers.md)
- [`docs/roadmap.md`](docs/roadmap.md)
- [`docs/compliance-considerations.md`](docs/compliance-considerations.md)
- [`docs/ml-architecture.md`](docs/ml-architecture.md) — ML subsystem pipeline
- [`docs/ml-limitations.md`](docs/ml-limitations.md) — **read before trusting any ML output**
