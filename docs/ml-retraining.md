# ML retraining

## How to retrain today

Retraining is **entirely manual** in Phase 1 — there is no scheduled
retraining job. An admin calls:

```
POST /api/v1/ml/train
{
  "market": "US",
  "horizon": "5D",
  "family": "logreg",
  "cost_bps": 3.0,
  "seed": 0,
  "calibrate": "isotonic"
}
```

This always creates a **new** `ml_models` row (new `code`, new
`model_version`) — it never mutates an existing model's artifact or
metrics. The new model starts at `state=SHADOW`. Promoting it to
`CHAMPION` is a separate, explicit action
(`POST /models/{id}/promote`) — retraining and deployment are
intentionally decoupled, per spec.

## Why no automatic schedule exists yet

The spec calls for configurable schedules (monthly for daily equity
models, weekly/monthly for crypto, event-triggered on major data
changes). Phase 1 does not implement a Celery beat entry for
`train_model` because:

1. Automatic retraining without automatic promotion is safe but
   produces an ever-growing set of `SHADOW` models with no review —
   not useful without the Phase 4 monitoring/comparison layer to
   triage them.
2. Retraining cadence should be tied to data-provider refresh cadence
   (see `docs/data-providers.md`), which itself isn't yet running on a
   production schedule for US/VN (both are credential-gated and
   currently unconfigured in the demo deployment).

## What IS scheduled today

Two Celery beat entries exist in `services/ml_worker/mlw/celery_app.py`:

| Task | Schedule | Purpose |
|---|---|---|
| `mlw.tasks.generate_predictions` | hourly, `:15` | Refresh predictions for every `SHADOW`/`CHAMPION` model against current bars |
| `mlw.tasks.evaluate_outcomes` | daily, 01:00 UTC | Score predictions whose horizon has expired |

Neither of these retrains a model — they only run inference against
already-trained artifacts and score past predictions.

## Adding a retraining schedule (future work)

The natural extension is a new beat entry,
`mlw.tasks.retrain_all_champions`, that:

1. Enumerates distinct `(market, horizon, task)` tuples with a current
   `CHAMPION`.
2. Calls the same `train_model` logic used by the manual endpoint,
   producing a new `EXPERIMENTAL`/`SHADOW` candidate.
3. **Does not auto-promote.** The new candidate sits in `SHADOW`
   alongside the existing `CHAMPION` until a human (or, once built, an
   automated champion/challenger comparison job) promotes it.

This keeps "retraining creates a candidate" and "promotion deploys a
candidate" as two separate, auditable actions — exactly the spec's
requirement that "retraining must not automatically replace the
production model."

## Event-triggered retraining

Not implemented. Would require detecting "major data or feature
changes" (e.g. a `FEATURE_VERSION` bump, a large backfill in
`price_bars`) and enqueueing training — currently a manual judgment
call by whoever changes the pipeline code.
