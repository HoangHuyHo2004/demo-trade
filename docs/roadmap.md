# Roadmap

Ordered per the product spec §20.

## Phase 1 — Foundation ✅ (this iteration)

- Monorepo + Docker Compose
- Async FastAPI + Postgres + Redis + Alembic
- Canonical asset identity + symbol resolution
- Deterministic mock provider (US / VN / crypto + benchmarks)
- Watchlist CRUD (demo user)
- Market status via trading calendars
- Next.js dashboard, watchlist, asset detail (sparkline chart)
- CI (lint + type + test + build), pytest suite for Phase 1 code

## Phase 2 — Market data + charts ✅

- Real adapters shipped:
  - Coinbase public REST (no auth) — active by default
  - Alpaca (US) — auto-selects when credentials present
  - SSI FastConnect (VN) — credential-gated skeleton (auth flow deferred)
- Historical bars persisted through `BarRepository` (DB-first, upserts,
  audited via `bar_ingest_runs`)
- Interactive Lightweight Charts on asset detail; period selector
  1D / 1W / 1M / 3M / 6M / 1Y / 5Y / MAX; per-period return badges
- Multi-asset compare page (up to 5), rebased-to-100 overlay, currency
  mismatch warning
- US + VN holidays for 2025–2027 in calendars; half-day sessions still
  deferred
- Data-freshness badge + provider-status panel in the UI
- Celery `refresh_bars` beat job populates cache for tracked assets

## Phase 3 — Signal + backtest engines ✅

- Pure-function indicator library (SMA, EMA, MACD, RSI, ATR, realized vol,
  MDD, momentum, breakout, rvol z-score, relative strength) with
  hand-computed fixture tests
- Rule-based ensemble `ensemble-v1` with trend / momentum / volatility /
  volume / benchmark factors, versioned `SignalModel` interface
- Signal engine: classification, heuristic confidence, ATR-based risk
  class, reference entry/invalidation/take-profit levels (only when
  defensible), full payload matching `packages/contracts/src/signals.ts`
- API: `GET /signals/{id}?horizon=`, `POST /signals/calculate`;
  persists `Signal` + `SignalFactor` rows with `data_version` + `strategy_version`
- Walk-forward backtester with strict `available_at` no-lookahead
  safeguard (asserted in tests), cost profiles per market, decision-at-t
  execution at t+1 open, benchmarks (buy&hold, cash, SMA 50/200,
  market benchmark)
- API: `POST /backtests`, `GET /backtests/{id}`
- Signal Laboratory page (`/lab/{id}`): factor bar chart, parameter form,
  cost overrides, equity-curve chart, metrics vs baselines
- Signal card on asset detail
- Methodology docs: `signal-methodology.md`, `backtesting-methodology.md`,
  `model-risk-management.md`

Deferred to a Phase 3.1 backlog:

- Walk-forward *parameter search* with locked out-of-sample verification
- Fundamentals overlays (needs paid data), crypto-specific overlays
  (funding rate / open interest)
- Point-in-time universe membership for VN delistings
- Empirically-calibrated confidence table

## Phase 4 — AI research agent ✅

- Pluggable LLM provider abstraction: `MockLLMProvider` (deterministic,
  demo/CI default) + `AnthropicProvider` (real Claude, credential-gated)
- Typed tool allowlist with `extra="forbid"` Pydantic schemas: resolve,
  market status, quote, historical bars, calculated indicators, signal,
  backtest, compare
- Search-tool skeletons (SEC / VN disclosures / IR announcements / crypto
  project posts / curated news) — always return `not_available` so the
  agent abstains honestly
- Orchestrator with delimited `<untrusted_source>` wrapping, per-turn
  budgets (tool calls / tokens / wall-clock / cost), redacted audit trail
  (`agent_runs`, `tool_calls`, `audit_logs`, `sources` tables)
- Structured `ResearchResponse` with facts vs interpretation vs
  assumptions vs unknowns, plus citations panel
- Signal-engine boundary: agent may request a signal but cannot invent
  scores — enforced by mock LLM and asserted by tests
- API: `POST /agent/chat`, `GET /agent/runs/{id}`, `GET /research/{id}`
- Web: `/research` chat page + `ResearchResponseView` + link from asset
  detail
- Doc: `docs/agent-security.md`

Deferred to Phase 4.1:
- Real SEC EDGAR / VN disclosure ingest + `sources`/`document_chunks` RAG
  with `pgvector`
- Offline agent-evaluator that samples turns and audits signal-summary
  consistency
- Anthropic streaming responses in the UI

## Phase 5 — Paper portfolio + hardening ✅

- Paper portfolios with manual transactions (BUY/SELL/DEPOSIT/WITHDRAW/
  DIVIDEND/FEE); WAC cost basis; realized + unrealized P&L
- FX conversion service (dated fixed-rate table for demo mode)
- Multi-currency cash + base-currency valuation
- Portfolio risk analytics: allocation by asset/market, HHI concentration,
  historical vol + MDD, historical VaR 95%/99%, correlation matrix,
  stress scenarios (−5/−10/−20/−30% risk-asset shock)
- Security headers middleware (CSP, X-Frame-Options, Referrer-Policy,
  Permissions-Policy, HSTS in production)
- Request-ID middleware — binds into structured-log context + echoes
  X-Request-Id header
- Rate limiter — Redis-backed with in-memory fallback; per-rule buckets
- Audit-log rows on portfolio mutations
- Web `/portfolio` page: overview, positions table with per-position P&L,
  transaction form, risk breakdown with allocation bars and stress
  scenarios
- Docs: `docs/deployment.md`, `docs/operations-runbook.md`

## Phase 5.1 — Production auth ✅

- Auth.js v5 with GitHub OIDC + demo credentials provider
- Shared HS256 JWT session (PyJWT on the API side)
- `users.oauth_provider` + `oauth_account_id` (migration 0006)
- `/api/v1/auth/{me,demo-login,logout}`, middleware, `/signin` page
- 99 pytest tests

## Phase 5.2 — Spec gap-fill ✅

- Per-market signal weights (US / VN / crypto) — spec §8 no longer
  uses one weight table for every market
- Signal payload additive fields (spec §9): `data_source`,
  `data_freshness`, `model_version`, `expected_holding_period`,
  combined `warnings`. Historical fields remain as aliases.
- API surface aliases (spec §10): `/api/v1/assets/{id}/quote|bars|signal`
  delegate to the existing handlers; `/watchlists/{id}/assets` alias.
- `POST /api/v1/assets/compare` — backend counterpart of the web
  compare page.
- Async job pattern (spec §14): jobs table, `POST /backtests` returns
  202 + `{job_id}`, `GET /jobs/{id}` polls; Celery task runs the same
  inline runner as the sync path. `USE_SYNC_JOBS=true` runs inline
  (default for tests + demo installs without Redis).
- `user_settings` + `alerts` entities (spec §16). Settings API +
  `/settings` web page.
- Playwright critical-flow E2E (`pnpm --filter web e2e` against a
  running compose stack).
- Docs: `docs/assumptions.md`, `docs/local-development.md`,
  `docs/api.md`, `docs/security.md`, `docs/ai-agent.md`.
- 109 pytest tests; 8 migrations apply from empty.

## Backlog (post-MVP)

- pgvector RAG for SEC filings + VN disclosures + news (Phase 4.1)
- Offline agent-evaluator sampling turns for signal-summary consistency
- Anthropic streaming responses in the UI
- Walk-forward parameter search with locked out-of-sample verification
- Empirically-calibrated confidence table for `ensemble-v1`
- OpenTelemetry traces + Prometheus metrics endpoint
- Runtime-configurable rate-limit rules
- Tax-lot cost accounting (FIFO/LIFO/specific-lot)
- Half-day calendars + `exchange_calendars` integration
- WCAG axe scan in CI
- Full alerts UI (scheduler evaluates the table today; no user surface yet)
