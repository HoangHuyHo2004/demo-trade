# ML validation

## Walk-forward, not random split

`app.ml.datasets.make_walk_forward_folds(start, end, train_days,
val_days, test_days, embargo_days)` produces a list of
`WalkForwardFold(train_from, train_to, val_from, val_to, test_from,
test_to)` tuples:

- **Expanding train window**: every fold's `train_from` is the same
  (the dataset start); `train_to` grows by `step_days` each fold.
- **Rolling validation window**: `val_from = train_to + embargo_days`,
  `val_to = val_from + val_days`.
- **Optional test window**: only populated when there's enough
  remaining history after an additional embargo gap.
- **Embargo**: a gap (default `horizon_bars + 2` days in the training
  task) between train/val and val/test boundaries so a label whose
  horizon straddles the boundary can't leak information across it.

Tests:
- `test_walk_forward_folds_are_chronological_and_non_overlapping`
- `test_walk_forward_folds_train_window_expands`
- `test_walk_forward_folds_empty_when_insufficient_history`

## What Phase 1 actually runs

`mlw.tasks.train_model` calls `make_walk_forward_folds` with
`train_days = max(180, span//3)`, `val_days = max(30, span//8)`,
`test_days = 0` — Phase 1 does not carve out a separate locked test
period per training run; it evaluates on the rolling validation window
of each fold and persists per-fold metrics to `ml_training_runs`. A
model's `metrics_json` on `ml_models` is a **mean across all
successful folds**, not a single-shot metric.

**This is an intentional Phase 1 simplification, not the spec's full
requirement.** The spec calls for a locked final out-of-sample test
period that is used at most once for final reporting. Phase 1's
`test_days=0` default means every fold's validation window doubles as
what would normally be reported — acceptable for shadow-mode models
that don't yet influence production signals, but **not sufficient**
for promoting a model past `SHADOW` with confidence. Before wiring
ensemble integration (Phase 3), the training task should be extended
to hold out a true final fold with `test_days > 0` and report test
metrics separately from validation metrics used for model selection.

## Why prefit calibration, not cross-validated

`training.train_direction_model` fits the base estimator on the
train fold, then wraps it in
`sklearn.calibration.CalibratedClassifierCV(base, method=calibrate,
cv="prefit")` and calibrates using the **validation** fold — never the
locked test set. This matches the spec: *"Calibration must use
validation data, not the final test set."*

## No fitting on validation/test

`StandardScaler` (used in the logreg and ridge pipelines) is fit
inside `sklearn.Pipeline.fit(X_train, y_train)` only — `Pipeline.predict`/
`predict_proba` on validation data reuses the already-fitted scaler.
This is standard sklearn Pipeline behavior and prevents the classic
"fit the scaler on all data" leak.

## Hyperparameter search

**Not implemented in Phase 1.** Every baseline model uses fixed,
documented hyperparameters (see `services/ml_worker/mlw/models.py`):

| Family | Key params |
|---|---|
| `logreg` | `C=1.0`, `class_weight="balanced"`, `max_iter=500` |
| `rf` | `n_estimators=200`, `max_depth=6`, `min_samples_leaf=20` |
| `gbm` | `n_estimators=200`, `max_depth=3`, `learning_rate=0.05`, `subsample=0.8` |

No search loop exists yet, so the spec's "maximum trials" / "record
every tested configuration" requirements don't yet apply — there's
only ever one configuration per `family`. When a search is added, it
must optimize only on train+val (never the locked test set), cap
trials, and log every trial's config + score to a new table (not yet
created).

## Cross-sectional leakage prevention

Phase 1's dataset builder walks each asset's bar series independently
and applies the same walk-forward fold boundaries (by calendar date)
across all assets — so a US-equity dataset with 50 tickers has every
ticker's `bar_time`-based row assigned to the same fold based on
absolute date, which prevents time-based leakage across assets.

**Not yet implemented**: point-in-time universe membership (today's
active-asset list is used for all historical dates, which is a
survivorship-bias source — see `docs/ml-limitations.md`), delisted-asset
inclusion, and same-event purging across assets (e.g., an earnings date
shared by two correlated tickers isn't currently purged from both sides
of a fold boundary).

## Reproducibility

Every `ml_training_runs` row records `seed`, `config_json` (which
includes `fit_wallclock_ms` and `trained_at`), `train_from/to`,
`val_from/to`, and `metrics_json`. Given the same dataset (same
`dataset_version`) and the same `seed`, `logreg` and `ridge` are
exactly reproducible (deterministic solvers); `rf` and `gbm` are
reproducible up to sklearn's own determinism guarantees for a fixed
`random_state`, which holds for single-threaded fits
(`n_jobs=1` is set explicitly on the random forest for this reason).
