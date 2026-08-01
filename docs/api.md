# API

All routes are versioned under `/api/v1`. OpenAPI is served at
`/docs` (Swagger) and `/redoc` (ReDoc). This document is a hand-written
overview; the authoritative schema is the OpenAPI JSON at `/openapi.json`.

## Auth

Session cookie or Bearer JWT. See [`docs/security.md`](security.md).

- `POST /api/v1/auth/demo-login` — issues a session cookie for the
  demo user (returns 404 unless `DEMO_MODE=true`).
- `POST /api/v1/auth/logout` — clears the session cookie.
- `GET /api/v1/auth/me` — current user (requires session).

## Assets

- `GET /api/v1/assets/search?q=&market=&asset_type=&limit=`
- `GET /api/v1/assets/{canonical_id}`
- `GET /api/v1/assets/{canonical_id}/quote` — spec §10 alias of
  `/api/v1/prices/{id}/quote`
- `GET /api/v1/assets/{canonical_id}/bars?interval=&lookback_days=`
- `GET /api/v1/assets/{canonical_id}/signal?horizon=&model=`
- `POST /api/v1/assets/compare` — body: `{asset_canonical_ids[2..5],
  interval, lookback_days}`. Returns aligned closes rebased to 100 +
  per-asset period return + currency-mismatch warning.

Canonical id format:

- Equity / ETF / index: `{TYPE}:{MARKET}:{EXCHANGE}:{SYMBOL}`
  (`EQUITY:US:NASDAQ:AAPL`, `EQUITY:VN:HOSE:VNM`, `INDEX:VN:HOSE:VNINDEX`)
- Crypto: `CRYPTO:{EXCHANGE}:{SYMBOL}` (3-part; market == exchange)
  e.g. `CRYPTO:COINBASE:BTC-USD`

## Prices (legacy path, still supported)

- `GET /api/v1/prices/{canonical_id}/quote`
- `GET /api/v1/prices/{canonical_id}/bars?interval=&lookback_days=`

Response includes `source`, `from_cache`, `last_bar_time`,
`last_ingest_time` for freshness display.

## Markets + providers

- `GET /api/v1/markets/status` — one row per calendar (XNYS, XHOS, XHNX,
  UPCOM, 24x7). Includes `is_open`, `next_open_utc`, `next_close_utc`.
- `GET /api/v1/providers/status` — per-provider status +
  `is_selected_for` (which markets each provider currently serves).

## Signals

- `GET /api/v1/signals/{canonical_id}?horizon={1D,5D,20D}&model=`
- `POST /api/v1/signals/calculate` — body:
  `{asset_canonical_id, horizon, model, as_of?}`

Payload includes both the spec §9 field names (`model_version`,
`data_source`, `data_freshness`, `expected_holding_period`, `warnings`)
and the historical aliases (`strategy_version`, `expected_holding_days`,
`liquidity_warnings`, `contradictions`, `data_fresh_seconds`) so old
clients don't break. See `docs/signal-methodology.md`.

Classifications: `STRONG_BULLISH`, `BULLISH`, `NEUTRAL`, `BEARISH`,
`STRONG_BEARISH`, `AVOID_HIGH_RISK`, `INSUFFICIENT_DATA`.

## Backtests

- `POST /api/v1/backtests` — enqueues an async job (spec §14).
  Returns **202** with `{job_id, kind, status, progress, ...}`.
  Poll `GET /api/v1/jobs/{job_id}` for progress; `result` populated on
  `status: COMPLETE`.
- `POST /api/v1/backtests/sync` — legacy synchronous variant. Returns
  the full result in the body (201).
- `GET /api/v1/backtests/{run_id}` — read a persisted synchronous run.

Body:

```json
{
  "asset_canonical_id": "EQUITY:US:NASDAQ:AAPL",
  "interval": "1d",
  "horizon": "5D",
  "entry_threshold": 20,
  "exit_threshold": -5,
  "cost_bps": null,
  "slippage_bps": null,
  "start": null,
  "end": null
}
```

`cost_bps` / `slippage_bps` null → use the per-market defaults from
`app/quant/costs.py`. See `docs/backtesting-methodology.md`.

## Jobs (spec §14)

- `GET /api/v1/jobs/{job_id}` — returns
  `{job_id, kind, status, progress, message, created_at, started_at,
   finished_at, result}`.

Statuses: `QUEUED`, `COLLECTING_DATA`, `CALCULATING`,
`GENERATING_REPORT`, `COMPLETE`, `FAILED`.

## Watchlists

- `GET /api/v1/watchlists`
- `POST /api/v1/watchlists` — body: `{name}`
- `POST /api/v1/watchlists/{id}/items` — body:
  `{asset_canonical_id, note}`
- `DELETE /api/v1/watchlists/{id}/items/{item_id}`
- `POST /api/v1/watchlists/{id}/assets` — spec §10 alias
- `DELETE /api/v1/watchlists/{id}/assets/{item_id}` — spec §10 alias

## Portfolios

- `GET /api/v1/portfolios`
- `POST /api/v1/portfolios` — body: `{name, base_currency}`
- `GET /api/v1/portfolios/{id}` — valuation with positions + P&L
- `POST /api/v1/portfolios/{id}/transactions` — body: `{kind, ...}`
  where kind is `BUY | SELL | DEPOSIT | WITHDRAW | DIVIDEND | FEE`
- `GET /api/v1/portfolios/{id}/risk?lookback_days=` — HHI, historical
  VaR, correlation matrix, stress scenarios

## Agent / research

- `POST /api/v1/agent/chat` — body: `{prompt, asset_canonical_id?,
  max_tool_calls?, max_output_tokens?}`. Returns `AgentChatResponse`
  with the structured `ResearchResponse` + `run_id` + `status`.
- `GET /api/v1/agent/runs/{id}` — audit view of a specific turn.
- `GET /api/v1/research/{canonical_id}` — one-shot canonical research
  summary (no chat).

See `docs/ai-agent.md`.

## Machine learning (ML Phase 1 — shadow-only)

Reads are open to any signed-in user. Writes (`train`, `promote`,
`shadow`, `disable`) require `users.is_admin = true` (403 otherwise).
See `docs/ml-architecture.md` for the pipeline and
`docs/ml-limitations.md` before trusting any output.

- `GET /api/v1/ml/models` — list all registered models
- `GET /api/v1/ml/models/{id}` — one model
- `GET /api/v1/ml/models/{id}/metrics` — model + its training-run history
- `GET /api/v1/ml/predictions/{canonical_id}?horizon=` — latest
  prediction, or `{status: "INSUFFICIENT_DATA"}` if none exists
- `GET /api/v1/ml/predictions/{canonical_id}/history?limit=` — past
  predictions for this asset (append-only, never rewritten)
- `POST /api/v1/ml/train` (admin) — body: `{market, horizon, family,
  cost_bps, seed, calibrate}`. Enqueues a Celery task on `ml_worker`;
  returns `202 {status: "queued", task_id}` or `503` if the broker is
  unreachable.
- `POST /api/v1/ml/models/{id}/shadow` (admin) — force `SHADOW` state
- `POST /api/v1/ml/models/{id}/promote` (admin) — `SHADOW → CHAMPION`;
  demotes any existing champion for the same `(market, horizon, task)`
  to `CHALLENGER`
- `POST /api/v1/ml/models/{id}/disable` (admin) — any state → `DISABLED`

**Every ML prediction response carries `shadow_only: true` and a
disclaimer.** No ML output is merged into `GET /api/v1/signals/{id}` —
they are served from entirely separate tables and endpoints.

## Settings (spec §12 + §16)

- `GET /api/v1/settings`
- `PATCH /api/v1/settings` — partial update of user + user_settings.
  Fields: `base_currency`, `locale`, `timezone`, `risk_display`
  (`BOTH | LEVEL_ONLY | SCORE_ONLY`), `signal_horizon_default`
  (`1D | 5D | 20D`), `theme` (`system | light | dark`),
  `notifications_email`.

## Ops

- `GET /health` — liveness (never touches DB)
- `GET /ready` — readiness (`SELECT 1` against the DB)

## Response conventions

- Timestamps: UTC ISO-8601 (`2026-08-01T00:00:00Z`).
- Money: **string-typed Decimals**, never float. The client is expected
  to parse via `Number()` (or a decimal library for precision-critical
  paths).
- Errors: FastAPI default `{detail: "..."}`. State-changing routes emit
  `409` on unique-constraint conflicts, `404` on missing asset/portfolio,
  `422` on schema validation, `429` on rate-limit trip.

## Rate limits

Written to every response as `X-Request-Id` header; `429` responses also
carry `Retry-After`. Default buckets (see
`app/core/middleware.py::RateLimitMiddleware`):

| Rule                          | Limit / window  |
| ----------------------------- | --------------- |
| `POST /api/v1/agent/chat`     | 10 / 60s        |
| `POST /api/v1/backtests`      | 20 / 60s        |
| `POST /api/v1/signals`        | 60 / 60s        |
| `POST /api/v1/portfolios`     | 60 / 60s        |
| All other writes              | 300 / 60s       |
