# ML model registry

## Table: `ml_models`

One row per trained model version. Key columns:

| Column | Meaning |
|---|---|
| `code` | Unique human-readable id, e.g. `us-direction-logreg-0.1.0` |
| `family` | `logreg` \| `ridge` \| `rf` \| `gbm` \| `ensemble` |
| `market` | `US` \| `VN` \| `COINBASE` |
| `horizon` | `1D` \| `5D` \| `20D` |
| `task` | `direction` \| `regression` \| `volatility` \| `drawdown` (Phase 1 only trains `direction`) |
| `model_version` | Stamped from family+market+horizon+dataset-version suffix |
| `dataset_version` | Links to `ml_datasets.dataset_version` used for training |
| `feature_version` / `target_version` | Pipeline versions at training time |
| `state` | See state machine below |
| `metrics_json` | Mean/min/max of `roc_auc`, `pr_auc`, `log_loss`, `brier`, `accuracy` across folds |
| `artifact_path` / `artifact_sha256` | Where the joblib file lives + its checksum |
| `approved_by_user_id` / `approval_note` | Set on promote/disable/shadow transitions |

## State machine

```
EXPERIMENTAL --(training completes with ≥1 successful fold)--> SHADOW
SHADOW --(admin: POST /models/{id}/promote)--> CHAMPION
CHAMPION --(admin promotes a different model)--> CHALLENGER
any --(admin: POST /models/{id}/disable)--> DISABLED
```

`VALIDATED`, `DEGRADED`, `RETIRED` are defined in the schema
(`MLModelState` enum) but **not yet driven by any code path** in
Phase 1 — they're reserved for Phase 4 (drift monitoring auto-
degrades a model) and a future explicit validation gate between
`EXPERIMENTAL` and `SHADOW`.

**Only `SHADOW` and `CHAMPION` models generate predictions** — the
hourly `generate_predictions` task filters on exactly those two
states (`mlw/tasks.py::_generate_predictions_async`).

**No model influences the user-facing rule-based signal in Phase 1,
regardless of state.** `CHAMPION` in the current codebase means
"the model shown as champion in the registry," not "the model whose
predictions replace or blend into `Signal`." Ensemble integration
(spec's actual mixing logic) is Phase 3.

## Promotion rules enforced today

`POST /api/v1/ml/models/{id}/promote`:

1. Requires `CurrentAdminDep` (403 otherwise).
2. Rejects if the model is `DEGRADED`, `DISABLED`, or `RETIRED`.
3. Rejects if `artifact_sha256` is null (no saved artifact — can't
   promote something with nothing to load at inference time).
4. Demotes any existing `CHAMPION` in the same `(market, horizon,
   task)` to `CHALLENGER` — there is only ever one champion per
   market/horizon/task tuple.
5. Records `promoted_at`, `approved_by_user_id`, `approval_note`.

**Not yet enforced** (spec's full "Model promotion requirements"
list): beating baselines, calibration acceptance thresholds, minimum
trade/observation counts, multi-period stability, max-drawdown limits,
latency checks, security checks, or a formal explainability report
attached to the promotion. Phase 1's promote endpoint is a manual
admin action with structural guards only — the *decision* to promote
is entirely a human judgment call today, which is explicitly allowed
("Model promotion must require an explicit approval record" — Phase 1
delivers the approval record, not automated gating).

## Model card requirement

The spec asks for a model card per production model (intended use,
prohibited use, limitations, etc.). Phase 1 does not auto-generate
these. Until that's built, treat `docs/ml-limitations.md` as the
model card for every Phase 1 model — the limitations documented there
apply uniformly to every `logreg`/`rf`/`gbm` direction model regardless
of market, because they all share the same feature pipeline, dataset
builder, and training loop.

## Querying the registry

```
GET  /api/v1/ml/models                 → list all (any signed-in user)
GET  /api/v1/ml/models/{id}             → one model
GET  /api/v1/ml/models/{id}/metrics     → model + its training-run history
POST /api/v1/ml/train                   → enqueue training (admin)
POST /api/v1/ml/models/{id}/shadow      → force SHADOW (admin)
POST /api/v1/ml/models/{id}/promote     → SHADOW → CHAMPION (admin)
POST /api/v1/ml/models/{id}/disable     → any → DISABLED (admin)
```
