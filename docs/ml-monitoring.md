# ML monitoring

**Status: not implemented in Phase 1.** This document describes what
exists (the data foundation for monitoring) and what's explicitly
deferred to Phase 4 per the spec's implementation order.

## What exists today (the raw material for monitoring)

- **`ml_predictions`**: every prediction is saved before its outcome is
  known, with `as_of`, `model_version`, `data_version`, and the full
  probability/confidence payload. This is append-only.
- **`ml_prediction_outcomes`**: a daily Celery task
  (`mlw.tasks.evaluate_outcomes`) finds predictions whose horizon has
  expired and writes the realized outcome — `actual_return`,
  `actual_direction`, `was_correct`, `calibration_bucket`. One row per
  prediction, written once, never rewritten (`data_was_corrected` flag
  exists for the rare case a provider corrects historical data, but no
  code currently sets it to `true` — that's also deferred).
- **`ml_training_runs.metrics_json`**: every fold's evaluation metrics,
  queryable per model via `GET /api/v1/ml/models/{id}/metrics`.

Given these two tables, a monitoring job (not yet written) could
compute rolling accuracy/calibration/log-loss over the last N
`ml_prediction_outcomes` rows per model and compare against the
training-time metrics to detect drift — the schema supports this
query pattern today.

## What's deferred to Phase 4

- **Data drift**: feature-distribution shift detection (population
  stability index, range checks) — not implemented.
- **Prediction drift**: monitoring the distribution of `prob_positive`
  / `confidence` over time for a given model — not implemented.
- **Performance drift**: automated comparison of rolling
  `ml_prediction_outcomes` accuracy against the training-time baseline
  — not implemented.
- **Automatic model degradation**: no code path ever sets
  `ml_models.state = DEGRADED`. This must be a human decision today
  (`POST /models/{id}/disable`).
- **Alerts / audit-log integration**: `AuditLog` rows are written for
  portfolio and auth events elsewhere in the app, but no ML-specific
  event (e.g. `ml_model_degraded`) is emitted yet.
- **Latency monitoring**: prediction generation runs as a Celery beat
  task on an hourly schedule; there is no per-prediction latency
  tracking.

## Recommended first monitoring job (not yet built)

A daily Celery task that, for each `SHADOW`/`CHAMPION` model:

1. Pulls the last 30 days of `ml_prediction_outcomes` joined to
   `ml_predictions` for that model.
2. Computes realized accuracy, Brier score, and mean calibration error
   (bucket-level `mean_pred` vs `actual_positive_rate`).
3. Compares against the model's `ml_training_runs` validation metrics.
4. If realized accuracy drops more than a configured threshold below
   validation accuracy (e.g. 10 percentage points) for two consecutive
   evaluation windows, flags the model — initially by writing an
   `audit_logs` row and leaving the state change to a human, later by
   automatically transitioning to `DEGRADED`.

This is explicitly a Phase 4 deliverable, listed here so the schema
decisions made in Phase 1 (append-only predictions/outcomes, versioned
models) are visibly aimed at supporting it.
