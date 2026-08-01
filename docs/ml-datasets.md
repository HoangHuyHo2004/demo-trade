# ML datasets

## Source of truth

Every ML dataset is built from `price_bars` — the same table the rule-
based signal engine and backtester read. There is no separate "ML data
lake"; this keeps point-in-time semantics consistent across the whole
app (one `available_at` gate, one calendar model, one cost-profile
table).

## Point-in-time guarantee

`app.ml.datasets.build_dataset` queries:

```sql
SELECT * FROM price_bars
WHERE asset_id = :asset_id AND interval = :interval
  AND bar_time >= :from_time         -- optional
  AND available_at <= :to_time       -- optional, defaults to unbounded
ORDER BY bar_time ASC
```

If `to_time` is set (as it always should be for a training run whose
test period is locked), bars that became available to the strategy
*after* `to_time` are excluded — even if their `bar_time` is earlier.
This matters for corporate-action adjustments and delayed provider
publication: a bar can exist with an early `bar_time` but a late
`available_at` if the provider republished it.

Test: `tests/test_ml_datasets.py::test_dataset_excludes_bars_not_yet_available`.

## Row construction

For each asset in the requested market, the builder walks bar index
`t` from `warmup_bars` to `len(bars) - horizon_bars - 1`:

- **Features** are computed from `closes[:t+1]`, `highs[:t+1]`, etc. —
  i.e., only bars up to and including `t`. The feature functions never
  see index `t+1` or later (they're just slicing; see
  `docs/ml-feature-dictionary.md`).
- **Labels** are computed from `closes[t : t+horizon+1]` — the future
  window. Labels are intentionally future-looking (that's what makes
  them labels); the leakage risk is if a *feature* accidentally used
  this window, which the feature functions structurally cannot do
  since they only receive the truncated slice.

Rows with a `None` label (insufficient history for the horizon) are
dropped.

## Universe

`Asset` rows where `market = <requested>` and `is_active = true`.
Phase 1 does not yet implement delisted-asset inclusion or point-in-
time universe membership (spec's stricter cross-sectional requirement)
— the current universe is "whatever is active today," which is a
known survivorship-bias source flagged in `docs/ml-limitations.md`.

## Dataset versioning

`compute_dataset_version()` hashes:

```
FEATURE_VERSION + TARGET_VERSION + UNIVERSE_VERSION
+ market + interval + horizon + cost_bps
+ from_time + to_time
+ sorted(universe canonical ids)
```

into a 12-byte blake2b digest, prefixed `ds-`. Same inputs → same
version, always (tested:
`tests/test_ml_datasets.py::test_dataset_version_is_deterministic`).
Any of the following bumps the version: a code change to feature
computation, a target-definition change, a different cost assumption,
a different date range, or a different asset universe.

Each unique `dataset_version` gets exactly one `ml_datasets` row
(created lazily on first training run that produces it), recording
`row_count`, `from_time`, `to_time`, and the three sub-versions.

## Sizing

- `warmup_bars` defaults to 200 — enough for the slowest feature
  (`price_over_ema200`) to be non-NaN.
- `max_rows_per_asset` caps very long histories (default 3000) by
  striding rather than dropping — keeps training tractable without
  biasing toward recent data only.
- Training requires at least 200 total rows across the universe or the
  worker task returns an error rather than fitting on too little data.

## What's deferred

- Fundamental / corporate-event / macro feature groups (spec lists
  these; Phase 1 ships price/volume-derived features only — see
  `docs/ml-feature-dictionary.md` for the exact list shipped).
- Point-in-time universe membership + delisted-asset inclusion.
- Cross-sectional purge (same-event overlap across assets) — Phase 1's
  embargo is time-based per walk-forward fold, not yet asset-pair
  aware.
