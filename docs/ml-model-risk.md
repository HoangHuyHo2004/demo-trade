# ML model risk

Companion to `docs/model-risk-management.md` (which covers the
rule-based signal engine). This document covers risk specific to the
machine-learning subsystem.

## The core risk control: shadow-only in Phase 1

Every ML model, regardless of `state`, is **read-only with respect to
user-facing signals**. `GET /api/v1/signals/{id}` (the rule-based
engine's endpoint) has zero code path that reads from `ml_models` or
`ml_predictions`. The only way ML output reaches a user is the
separate `GET /api/v1/ml/predictions/{id}` endpoint and the
`MLPredictionCard` component, which is permanently labeled
`SHADOW · does not influence signal` regardless of the underlying
model's registry state (including `CHAMPION`) until ensemble
integration ships.

This means the single biggest Phase-1-specific model risk — a bad
model corrupting the platform's primary trading signal — is
structurally impossible today, not just policy-guarded.

## Risks that DO apply today

### 1. Training-data quality risk (mock data)

Per `docs/assumptions.md`, US and VN model families in this repository
were trained against the deterministic mock provider's synthetic GBM
data unless real Alpaca/SSI credentials are configured. **A model
trained on synthetic data has learned nothing about real market
structure.** Its `ml_models.metrics_json` will look plausible (mock
data has genuine autocorrelation structure from the GBM drift term)
but says nothing about real predictive skill. Crypto models trained
against real Coinbase history are the only Phase 1 models with any
claim to real-world signal.

**Mitigation**: `docs/ml-limitations.md` must be read before trusting
any US/VN model's metrics. The `ml_models.dataset_version` and
`ml_datasets` row for any model record exactly which bars it trained
on — an operator can audit whether real or mock data was used by
checking the `PriceBar.source` column for the training window.

### 2. Overfitting via too-few walk-forward folds

Phase 1's default fold sizing (`train_days = max(180, span//3)`, etc.)
was chosen for demo-data volumes (mock provider ships ~1 year of
history by default). With only 1-2 years of history, a model may get
2-3 folds — too few to assess stability across regimes. The
`metrics_json.folds` count on every model is exposed via
`GET /models/{id}` precisely so this is visible, not hidden.

**Mitigation**: don't promote a model with `folds < 3` to `CHAMPION`
without manually reviewing per-fold metrics via
`GET /models/{id}/metrics`.

### 3. Class imbalance in the direction label

The cost-adjusted neutral zone (see `docs/ml-targets.md`) can produce
very few `+1`/`-1` examples relative to `0` in low-volatility windows
— but since neutral rows are **dropped** before training (not treated
as a third class), the realized issue is closer to "too few training
examples after filtering" than classic imbalance. `class_weight="balanced"`
is set on `logreg` and `rf` to reduce (not eliminate) skew within the
binary problem.

**Mitigation**: `ml_training_runs.metrics_json` records
`n_pos_train`/`n_pos_val` counts and `baseline_positive_rate` — a
model whose validation positive rate is near 0% or 100% should not be
trusted regardless of its accuracy score (accuracy on a degenerate
label is meaningless).

### 4. Calibration quality is unverified at inference time

Training computes calibration bins (`_reliability_bins` in
`training.py`) and stores them in `ml_training_runs.calibration_json`,
but **nothing currently checks calibration quality before allowing a
promote**. A model with a Brier score of 0.4 (poor) can still be
promoted to `CHAMPION` today.

**Mitigation**: this is the top Phase-1-to-Phase-3 gap. Until a
calibration-quality gate is added to the promote endpoint, promotion
decisions require a human to open `GET /models/{id}/metrics` and read
the calibration bins before approving.

### 5. Feature/label pipeline bugs propagate silently

Because `FEATURE_VERSION`/`TARGET_VERSION` only change when a human
edits the constant, a silent bug fix to `build_features()` that
doesn't bump the version would make old and new predictions
non-comparable while claiming the same version. This is a process
risk, not a code risk.

**Mitigation**: `AGENTS.md` and code comments in `app/ml/__init__.py`
state the rule; enforcement is currently human review, not CI-checked.

## Explicit non-goals for Phase 1

- No drift monitoring (Phase 4).
- No automatic model disabling on performance degradation (Phase 4).
- No out-of-distribution detection — a prediction is generated for any
  asset with ≥60 bars regardless of how unusual its current feature
  vector is relative to the training distribution.
- No SHAP or permutation importance — `feature_importance()` returns
  raw coefficients (logreg) or `feature_importances_` (rf/gbm), which
  are directionally useful but not causally rigorous. See
  `docs/ml-explainability.md`.
