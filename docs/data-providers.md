# Data providers

DEMO-TRADE depends only on the abstract interfaces in
`services/api/app/providers/base.py`. Concrete adapters live next to
them and are chosen at boot by `providers/registry.py`.

## Selection rules (Phase 2)

| Market   | Adapter                        | Selected when                                  |
| -------- | ------------------------------ | ---------------------------------------------- |
| COINBASE | `coinbase` (public REST)       | Always (public, no auth), unless `USE_MOCK_PROVIDERS_ONLY=true` |
| US       | `alpaca` if creds, else `mock` | `ALPACA_API_KEY` + `ALPACA_API_SECRET` both set |
| VN       | `ssi-fc` if creds, else `mock` | `SSI_FC_CONSUMER_ID` + `SSI_FC_CONSUMER_SECRET` both set |
| any      | `mock`                         | fallback; also forced by `USE_MOCK_PROVIDERS_ONLY=true` |

Every registered provider — even inactive ones — appears in
`/api/v1/providers/status` with fields `status`, `markets`, and
`is_selected_for`, so operators can see which market each request is
being routed to.

## Adapter status

| Slug        | Kind          | Markets  | Auth needed                        | Status      | License notes                              |
| ----------- | ------------- | -------- | ---------------------------------- | ----------- | ------------------------------------------ |
| `mock`      | market_data   | all      | none                               | ✅ shipped  | own-generated data — no license concern    |
| `coinbase`  | market_data   | crypto   | none (public feed)                 | ✅ shipped  | Public exchange feed; per-exchange price   |
| `alpaca`    | market_data   | US       | `ALPACA_API_KEY`, `ALPACA_API_SECRET` | ✅ shipped, credential-gated | Free IEX tier; check redistribution ToS |
| `ssi-fc`    | market_data   | VN       | `SSI_FC_CONSUMER_ID/SECRET`        | 🚧 skeleton (auth flow deferred) | Requires signed SSI contract |

## Bar caching + fallback

Historical bars flow through `BarRepository`:

1. Read the requested window from `price_bars`.
2. If we have <60% of the expected bar count, call the provider.
3. Upsert results on the `(asset, interval, bar_time, source)` unique key.
4. Record a row in `bar_ingest_runs` with counts + status (audited).
5. If the provider raises, serve whatever cache we had; the failure is logged
   with the exception, and a `bar_ingest_runs` row is written with
   `status="error"`.

The `/api/v1/prices/{id}/bars` response exposes `from_cache`,
`last_bar_time`, and `last_ingest_time` so the UI can render a
freshness badge without a second request.

## Rules (from `AGENTS.md` §5)

- No unofficial scraped endpoints in production code.
- Never assume public redistribution rights — document each adapter's
  ToS position in `docs/data-licensing-checklist.md` before shipping.
- Cross-exchange crypto prices are kept **separate** (per exchange); we
  do not fabricate a canonical "spot price".
- HTTP calls go through `app/providers/_http.py`, which enforces per-adapter
  host allowlists and adds retry with exponential backoff.
