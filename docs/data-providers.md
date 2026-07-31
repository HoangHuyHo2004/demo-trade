# Data providers

DEMO-TRADE depends only on the abstract interfaces in
`services/api/app/providers/base.py`. Concrete adapters live next to
them and are chosen at boot by `providers/registry.py`.

## Phase 1

| Slug   | Kind         | Markets                       | Auth | Status          |
| ------ | ------------ | ----------------------------- | ---- | --------------- |
| `mock` | market_data  | US · VN · COINBASE (all)      | none | ✅ implemented  |

The mock adapter is deterministic: `(canonical_id, interval, bar_index)`
seeds a GBM walk anchored at 2020-01-01, so overlapping windows always
agree and CI is reproducible.

## Phase 2 (planned)

| Slug        | Kind          | Markets  | Auth needed                        | License notes                             |
| ----------- | ------------- | -------- | ---------------------------------- | ------------------------------------------ |
| `alpaca`    | market_data   | US       | `ALPACA_API_KEY`, `ALPACA_API_SECRET` | Free tier; check redistribution ToS       |
| `sec-edgar` | filings       | US       | none                               | Public; abide by fair-use / rate limits    |
| `ssi-fc`    | market_data   | VN       | `SSI_FC_CONSUMER_ID/SECRET`        | Requires licensed contract with SSI       |
| `fiin`      | fundamentals  | VN       | contract-issued key                | Paid license required                     |
| `coinbase`  | market_data   | crypto   | none (public feed)                 | Public exchange data; per-exchange price   |
| `coingecko` | reference     | crypto   | optional API key                   | Free tier rate-limited                    |

## Rules (from `AGENTS.md` §5)

- No unofficial scraped endpoints in production code.
- Never assume public redistribution rights — document each adapter's
  ToS position in `docs/data-licensing-checklist.md` before shipping.
- Cross-exchange crypto prices are kept **separate** (per exchange); we
  do not fabricate a canonical "spot price".
