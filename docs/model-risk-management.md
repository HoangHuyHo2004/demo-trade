# Model risk management

This document tracks how DEMO-TRADE controls model risk. It complements
`docs/compliance-considerations.md`.

## Inventory

| Code            | Family    | Location                            | Purpose                              |
| --------------- | --------- | ----------------------------------- | ------------------------------------ |
| `ensemble-v1`   | ensemble  | `app/quant/ensemble.py`             | Explainable rule-based signal        |

The `SignalModelVersion` row is created lazily the first time a model is
used, from `code`, `family`, and `description`. Every persisted `Signal`
and `BacktestRun` references it via `model_version_id`, so it's always
possible to answer "which model produced this signal?".

## Versioning rules

- **Any change to factor definitions, weights, thresholds, or the
  score → classification mapping requires a new `code`.** Do not mutate
  `ensemble-v1` in place.
- **Non-behavioral refactors** (renaming an internal helper, adding a
  factor detail string) may keep the same code, but must be validated
  by re-running the reproducibility test.
- Deprecating a model: mark the row with a "deprecated_at" note in a
  follow-up migration (Phase 5).

## Determinism + reproducibility

- The indicator suite is a pure-function library with no I/O.
- The engine records a `data_version` hash so a "which bars did this
  signal see?" question is answerable from the DB.
- `test_signal_is_reproducible` and `test_backtest_is_deterministic`
  guard these properties.

## Data quality gate

Before classification, the engine requires:
- `data_quality >= 0.4` OR the classification is forced to
  `INSUFFICIENT_DATA`
- `n_bars >= 10` OR the payload short-circuits to the same

`data_quality` is a blend of factor-category coverage and observed bar
count. It is intentionally conservative — a model score alone does not
override missing evidence.

## Change management (recommended process before shipping ensemble-v2)

1. Land the new model behind a new code (`ensemble-v2`).
2. Backfill signals for the last 12 months for a representative universe.
3. Compare `ensemble-v1` vs `ensemble-v2` for score distribution,
   confidence calibration, hit rate by horizon, drawdown behavior.
4. Document the diff in `docs/signal-methodology.md`.
5. Only then flip the default model surface.

## Known model risks

- **Overfitting to synthetic data.** In demo mode the mock provider is
  a seeded GBM — models tuned on it will not generalize. Any parameter
  change validated against real market data before shipping.
- **Regime shift.** The ensemble uses simple percentile-free scaling.
  A regime with structurally higher volatility will produce systematically
  higher risk classifications; watch for downstream UI leaking that as
  "avoid" when it should say "size smaller".
- **Confidence is heuristic**, not empirically calibrated. Do not treat
  it as a probability.
- **Long-only bias.** Bear-market performance is not modeled; the score
  can go negative but the strategy simply flattens.
- **Data-provider stale bars.** If provider ingest lags, `available_at`
  guards prevent lookahead, but the model may operate on partial data.
  Watch `bar_ingest_runs` for gaps.
