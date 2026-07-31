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

## Phase 2 — Market data + charts

- Real adapters: Alpaca (US), SSI FastConnect (VN), Coinbase public (crypto)
- Historical bars persisted, adjustments applied
- Interactive TradingView Lightweight Charts, period comparison (1D…MAX)
- Half-day / holiday calendars, market-holiday tests
- Provider status + data-freshness banners driven by ingest jobs

## Phase 3 — Signal + backtest engines

- Explainable rule-based signal ensemble with factor contributions
- Confidence calibration from historical out-of-sample performance
- Walk-forward backtester with dated market-profile costs/slippage
- Signal laboratory UI
- Methodology docs (`docs/signal-methodology.md`, `docs/backtesting-methodology.md`)

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
