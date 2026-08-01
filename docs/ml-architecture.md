# ML architecture

**Status: ML Phase 1 (data + baseline models, shadow-only).** This
document describes what is implemented today, not the full spec's
eventual system. See `docs/roadmap.md` for what's deferred.

## Pipeline (spec architecture, as built)

```
Market data (price_bars, available_at-gated)
    ↓
Point-in-time dataset builder (app/ml/datasets.py)
    ↓
Feature pipeline v1 (app/ml/features.py — 28 features, pure functions)
    ↓
Rule-based signal engine (app/quant/ensemble.py — UNCHANGED, still authoritative)
    ↓
ML baseline models (services/ml_worker — logreg / rf / gbm, SHADOW only)
    ↓
[ensemble integration — NOT YET BUILT, Phase 3]
    ↓
ml_predictions table (spec-shaped payload) → GET /api/v1/ml/predictions/{id}
    ↓
AI agent may explain (not yet wired — Phase 3/agent tool addition)
```

**The critical invariant**: ML predictions are saved to their own table
(`ml_predictions`) and read through their own endpoint
(`/api/v1/ml/predictions/{id}`). They are **never merged into**
`Signal` from the rule-based engine. The web UI renders them in a
separate card labeled `SHADOW · does not influence signal`. This
satisfies spec's core constraint: *"The machine-learning system must
supplement the explainable rule-based signal engine rather than
immediately replacing it."*

## Why two services

`services/api` stays free of scikit-learn / numpy / pandas / joblib —
those are ~150MB of dependencies that don't belong in the low-latency
request path. `services/ml_worker` is a separate Celery app
(`mlw.celery_app`) that:

1. Imports the api's pure-Python pipeline code (`app.ml.*`) via
   `PYTHONPATH` — no duplication of feature/label logic.
2. Owns the heavy ML deps (scikit-learn, joblib) and does all model
   fitting, calibration, and artifact I/O.
3. Talks to the same Postgres via its own SQLAlchemy session — reads
   `price_bars`, writes `ml_models` / `ml_training_runs` /
   `ml_predictions`.

The API's `/api/v1/ml/train` endpoint enqueues a task by name
(`mlw.tasks.train_model`) rather than importing scikit-learn directly.
If the Celery broker is unreachable, the endpoint returns `503` rather
than hanging or crashing.

## Module map

```
services/api/app/ml/
  __init__.py       FEATURE_VERSION / TARGET_VERSION / UNIVERSE_VERSION
  features.py        28-feature pipeline, pure functions, no I/O
  labels.py           direction / regression / vol / drawdown targets
  datasets.py         point-in-time dataset builder + walk-forward folds

services/api/app/api/v1/ml.py   FastAPI routes (read: any user; write: admin)
services/api/app/models/ml.py   ml_models / ml_datasets / ml_training_runs /
                                 ml_predictions / ml_prediction_outcomes

services/ml_worker/mlw/
  celery_app.py       Celery app + beat schedule
  models.py            sklearn model wrappers (logreg / rf / gbm / ridge)
  training.py           fit → calibrate → evaluate for one fold
  tasks.py               train_model / generate_predictions / evaluate_outcomes
```

## Data flow: training a model

1. Admin calls `POST /api/v1/ml/train` with `{market, horizon, family,
   cost_bps}`.
2. API validates the request, enqueues `mlw.tasks.train_model` on the
   Celery broker, returns `202 {status: "queued", task_id}`.
3. Worker builds a dataset (`app.ml.datasets.build_dataset`) — this
   reads `price_bars` filtered by `available_at <= to_time` (default:
   now), computes features + labels per asset, returns a flat table
   with a deterministic `dataset_version` hash.
4. Worker computes walk-forward folds
   (`app.ml.datasets.make_walk_forward_folds`) — expanding train
   window, rolling validation window, embargo gap.
5. For each fold: fit on train, calibrate on validation
   (`CalibratedClassifierCV` with `cv="prefit"`), evaluate on
   validation, persist an `ml_training_runs` row with metrics +
   calibration bins.
6. After all folds: the final fold's fitted model is saved to disk
   (joblib, sha256-recorded), the `ml_models` row is created with
   `state=SHADOW`.
7. A separate beat-scheduled task (`generate_predictions`, hourly)
   walks every `SHADOW`/`CHAMPION` model and writes one
   `ml_predictions` row per covered asset.
8. A daily task (`evaluate_outcomes`) finds predictions whose horizon
   has expired and writes an `ml_prediction_outcomes` row — the actual
   return, whether the direction call was correct, the calibration
   bucket. **Existing prediction rows are never modified.**

## What is NOT built yet (see `docs/roadmap.md`)

- Ensemble integration (combining rule signal + ML probability into
  one score) — Phase 3 per spec's implementation order.
- Out-of-distribution detection.
- Champion/challenger automated comparison + drift monitoring.
- The AI agent explaining ML predictions (needs a new tool,
  `get_ml_prediction`, added to the allowlist — not yet added).
- Similar-pattern / nearest-neighbor search.
- Behavior profiles.
- XGBoost / LightGBM / deep learning (explicitly gated behind Phase 5
  in the spec — simple models must prove out first).
- Model-performance admin dashboard (data model supports it; no page
  yet).

## Design principles carried over from the rest of the app

- **Point-in-time correctness**: every dataset row uses only bars
  whose `available_at <= as_of`. Tested in
  `tests/test_ml_datasets.py::test_dataset_excludes_bars_not_yet_available`.
- **No silent rewrites**: `ml_predictions` rows are immutable once
  written; outcomes go in a separate table.
- **Versioned everything**: `FEATURE_VERSION`, `TARGET_VERSION`,
  `UNIVERSE_VERSION` constants in `app/ml/__init__.py`; any change to
  what a feature/label computes requires bumping the version so old
  predictions remain interpretable.
- **Admin-gated writes**: `POST /ml/train`, `/promote`, `/disable`
  require `users.is_admin = true`. Normal users can only read.
