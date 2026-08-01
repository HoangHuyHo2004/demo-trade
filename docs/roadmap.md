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

## ML Phase 1 — Data + baseline models (shadow-only) ✅

Machine-learning subsystem that **supplements** the rule-based signal
engine — never merged into it. See `docs/ml-architecture.md` for the
full pipeline diagram and `docs/ml-limitations.md` before trusting any
number it produces.

- Migration 0009: `users.is_admin` + `ml_models` (registry with
  EXPERIMENTAL/VALIDATED/SHADOW/CHAMPION/CHALLENGER/DEGRADED/DISABLED/
  RETIRED state machine) + `ml_datasets` + `ml_training_runs` +
  `ml_predictions` (saved before outcomes are known, immutable) +
  `ml_prediction_outcomes` (honest post-hoc scoring, never rewrites)
- `app/ml/features.py`: 28-feature pure-function pipeline (returns,
  trend, momentum, volatility, volume, benchmark-relative) —
  deterministic, no lookahead by construction (functions only ever see
  a truncated prefix of the bar series)
- `app/ml/labels.py`: cost-adjusted direction label + regression /
  volatility / drawdown targets, all computed from `closes[t:t+horizon+1]`
  only
- `app/ml/datasets.py`: point-in-time dataset builder
  (`available_at`-gated) + deterministic `dataset_version` hashing +
  walk-forward fold generator (expanding train, rolling val, embargo
  gap)
- **New service `services/ml_worker`**: separate Celery app carrying
  scikit-learn/joblib so the api stays lean. Baselines: `logreg`, `rf`,
  `gbm` (ridge reserved for regression, not yet trained). Isotonic/
  sigmoid probability calibration on the validation fold via
  `CalibratedClassifierCV` (version-compatible across sklearn
  ≥1.5 including the 1.6+ `FrozenEstimator` API change).
  Signed per-feature contributions for linear models; honest
  "unsigned importance only" fallback + warning for tree models (no
  SHAP dependency in Phase 1).
- API: `GET /api/v1/ml/models[/{id}[/metrics]]`,
  `GET /api/v1/ml/predictions/{id}[/history]`,
  `POST /api/v1/ml/train` (admin, enqueues Celery task, 503 if broker
  unreachable), `POST /models/{id}/{shadow,promote,disable}` (admin)
- Web: `MLPredictionCard` on asset detail — permanently labeled
  `SHADOW · does not influence signal`, shows probability, expected-
  return band, confidence, positive/negative contributors, and the
  model/data version footer
- Docs: all 11 spec-required ML docs (`ml-architecture`, `ml-datasets`,
  `ml-feature-dictionary`, `ml-targets`, `ml-validation`,
  `ml-model-registry`, `ml-model-risk`, `ml-monitoring`,
  `ml-retraining`, `ml-explainability`, `ml-limitations`)
- 34 new api pytest tests (features, labels, datasets, walk-forward
  folds, API admin-gating) — **143 total**, all green
- 12 ml_worker pytest tests against real scikit-learn (model fit/
  predict, signed contributions, save/load roundtrip, end-to-end
  training + calibration on synthetic data with a real signal) — found
  and fixed two real bugs during test-writing: an undefined-variable
  crash in contribution generation, and a scikit-learn 1.6+ API
  incompatibility (`cv="prefit"` removal)

**Deferred to ML Phase 2+** (per spec's own phased order): ensemble
integration (mixing ML output into the rule-based signal), out-of-
distribution detection, champion/challenger automated comparison,
drift monitoring + auto-disable, the AI agent explaining ML output (no
`get_ml_prediction` tool yet), similar-pattern/nearest-neighbor search,
behavior profiles, fundamental/corporate-event/macro feature groups,
hyperparameter search, XGBoost/LightGBM/deep learning, and the
admin model-performance dashboard.

## Backlog (post-MVP)

- pgvector RAG for SEC filings + VN disclosures + news (Phase 4.1)
- Offline agent-evaluator sampling turns for signal-summary consistency
- Anthropic streaming responses in the UI
- Walk-forward parameter search with locked out-of-sample verification
- Empirically-calibrated confidence table for `ensemble-v1`
- ML Phase 2: ensemble integration, OOD detection, calibration-gated promotion
- ML Phase 3: drift monitoring, champion/challenger, auto-disable
- ML Phase 4: model-performance admin dashboard, agent ML explanation tool
- OpenTelemetry traces + Prometheus metrics endpoint
- Runtime-configurable rate-limit rules
- Tax-lot cost accounting (FIFO/LIFO/specific-lot)
- Half-day calendars + `exchange_calendars` integration
- WCAG axe scan in CI
- Full alerts UI (scheduler evaluates the table today; no user surface yet)
