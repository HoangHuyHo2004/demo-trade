# Assumptions

Recorded per spec §1. Anything in this file is a decision that shaped
the code and can be reversed with a targeted refactor rather than a
rewrite.

## Repository inspection findings

The MVP already existed when this pass began. Nothing was scrapped; the
gap-fill work in Phase 5.2 (this iteration) added the missing spec
items on top of the tested implementation.

Reused as-is (well-tested, load-bearing):

- `services/api/app/quant/indicators.py` — pure functions (`ema`, `sma`,
  `rsi`, `macd`, `atr`, `realized_vol`, `momentum`, `rolling_zscore`,
  `breakout_status`, `relative_strength`, `max_drawdown`) with fixed-
  fixture tests. **No changes.**
- `services/api/app/services/backtester.py` — walk-forward engine with
  `available_at` no-lookahead guard, per-market cost profiles. Wrapped
  by a new async job wrapper in Wave 2; the engine itself is untouched.
- `services/api/app/services/bar_repository.py` — DB-first bar reads
  with provider fallback and audited upserts. **No changes.**
- `services/api/app/providers/*` — mock + Coinbase (public) + Alpaca +
  SSI FastConnect. Selection via credential-based registry. **No changes.**
- `services/api/app/agent/*` — orchestrator + tool executor + LLM
  abstraction. **No changes.** `AnthropicProvider` remains the
  production LLM; `MockLLMProvider` remains the demo default.
- `services/api/app/services/signal_engine.py` — engine core, kept.
  Only additive: payload gains new fields (`data_source`,
  `data_freshness`, `model_version`, `expected_holding_period`,
  `warnings`), old fields remain as aliases.
- `services/api/app/services/portfolio.py` + `risk.py` + `fx.py` — WAC
  math, allocations, HHI, historical VaR, correlation. **No changes.**

Refactored (targeted change, no behavior break):

- `services/api/app/quant/ensemble.py` — factor weights previously a
  single `_WEIGHTS` dict. Now a per-market weight profile map, dispatched
  by the asset's market at compute time. Existing tests still pass
  because US weights are unchanged from the original.

Added (new):

- Wave 1: `POST /api/v1/assets/compare`, `GET /api/v1/assets/{id}/quote`,
  `/bars`, `/signal` aliases pointing at the existing route handlers.
- Wave 2: `jobs` table + async backtest job pattern.
- Wave 3: `user_settings` + `alerts` tables. `/api/v1/settings` GET/PATCH.
  `/settings` web page.
- Wave 4: Playwright critical-flow test. New docs.

## Explicit assumptions

### Product / scope

- **Educational / research use only.** Every price and every signal in
  the UI carries the disclaimer. No real-money order execution is
  implemented and none is planned for the MVP.
- **US, VN (HOSE/HNX/UPCOM), and spot crypto (Coinbase)** are the
  supported markets. Other venues would require adding an adapter and
  extending `Market` in `app/domain/asset_id.py`.

### Signal engine

- **Rule-based ensemble is the reference model.** ML models can plug
  into `SignalModel` in `app/quant/models_base.py` without changing the
  API contract. Confidence is currently a heuristic blend of factor
  agreement + data quality + magnitude; empirical calibration against
  a locked out-of-sample table remains Phase 5.3 backlog.
- **Per-market weight profiles** were added in Wave 1 (US / VN /
  CRYPTO). Weights differ modestly. Every rule change requires a new
  `code` per `docs/model-risk-management.md`.
- **Long-only.** Short positions and pair trades are not modeled.

### Data providers

- **Coinbase public REST** is active by default because it needs no
  auth. All other real adapters are credential-gated and fall back to
  the deterministic mock. `USE_MOCK_PROVIDERS_ONLY=true` (set in tests)
  short-circuits the whole registry to the mock.
- **No unofficial scraped endpoints in production code.** SSI FastConnect
  is a credential-gated skeleton; it refuses to serve data without a
  signed contract.
- **Cross-exchange crypto prices are kept separate** (per exchange). We
  do not fabricate a canonical "spot price".

### Agent

- **Anthropic Claude Sonnet 5** is the production LLM.
- **Mock LLM is the demo/CI default** — deterministic script, never
  free-texts, exercises the full tool pipeline. Tests do not depend on
  a live LLM.
- **Tool result content is untrusted.** Wrapped in
  `<untrusted_source>...</untrusted_source>` before the model sees it.
  The `search_*` tools are skeletons that return `not_available` so the
  agent must abstain rather than fabricate citations.

### Auth + security

- **Auth.js in the web app + shared HS256 JWT session cookie**
  verified by PyJWT on the API. `AUTH_SECRET` must be identical in both
  services (docker-compose interpolation handles this).
- **`DEMO_MODE=true`** enables the credentials provider ("Continue as
  demo user"), auto-provisions the demo user on the API side, and
  exposes `POST /api/v1/auth/demo-login`. In production these paths are
  disabled.
- **Cross-origin session cookie** works in local dev (both services on
  `localhost`, same eTLD+1). Production topology must either share a
  domain or reverse-proxy `/api/v1/*` through Next.js.
- **Rate limiter** uses Redis when reachable; falls back to per-process
  in-memory, which is unsafe across multiple api replicas. Multi-
  process production MUST have Redis.

### Backtesting

- **Walk-forward evaluation** of fixed parameters only. Grid-search
  parameter tuning with locked out-of-sample verification is Phase 5.3
  backlog.
- **Wave 2** wraps the same synchronous engine behind a Celery job so
  long windows don't hit HTTP timeouts. The engine itself is unchanged.

### Portfolio

- **WAC (weighted-average cost)** basis. Tax-lot accounting (FIFO / LIFO
  / specific-lot) is deferred.
- **Historical VaR is percentile-based** on portfolio returns weighted
  by current allocation. Not a distributional model; not a guarantee.
- **Stress scenarios apply a uniform shock to risk assets** with cash
  unchanged. No sector or factor decomposition yet.

### Deliberately deferred

- pgvector RAG for SEC filings + VN disclosures + news
- Full WCAG audit (basics implemented via semantic HTML + keyboard-
  reachable controls; automated scan is Wave 5)
- OpenTelemetry / Prometheus metrics endpoint
- Runtime-configurable rate-limit rules
- WebSocket streaming for quotes (currently REST polling)
- Multi-currency portfolio VaR that decomposes FX risk from equity risk
