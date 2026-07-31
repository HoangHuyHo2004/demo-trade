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

## Phase 4 — AI research agent

- Single research agent with allow-listed typed tools (Claude/Anthropic)
- Source ingestion + structured citations
- Prompt-injection defense (delimited untrusted content, URL allowlist,
  budgets, per-turn token/cost/timeout caps)
- Research chat UI with tool activity, citations, and clear fact vs
  interpretation separation

## Phase 5 — Paper portfolio + hardening

- Manual paper transactions, positions, P&L, allocations, correlations
- Portfolio VaR + stress scenarios (informational)
- Real auth (Auth.js / OIDC), CSRF, rate limiting, security headers
- Observability, structured audit logs, WCAG sweep
- Playwright critical-flow tests
- Deployment (`docs/deployment.md`), runbook (`docs/operations-runbook.md`)
