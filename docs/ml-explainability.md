# ML explainability

## What's implemented

**Global feature importance**: `TrainedModel.feature_importance(names)`
in `services/ml_worker/mlw/models.py` returns a `dict[feature_name,
importance]`:

- For `logreg`/`ridge`: absolute value of the fitted coefficients,
  normalized to sum to 1.
- For `rf`/`gbm`: sklearn's native `feature_importances_` (Gini-based
  for RF, gain-based for GBM).

This is **not calibrated to a common scale across families** — a
logreg importance of 0.3 and a GBM importance of 0.3 are not directly
comparable magnitudes, only within-model rankings are meaningful.

**Per-prediction contributors**: `mlw.tasks._generate_predictions_async`
computes, for the current feature vector `x`, a rough per-feature
contribution as `importance[feature] * x[feature]` and stores the top
5 as `positive_contributors` in the `ml_predictions` row, matching the
spec's example shape:

```json
{
  "feature": "rel_strength_20",
  "value": 1.42,
  "contribution": 0.18
}
```

The `description` field in the spec's example is **not populated** in
Phase 1 — the API returns `feature`, `value`, `contribution` only. A
human-readable description per feature would need a lookup table
mapping feature names to plain-language explanations (the raw material
exists in `docs/ml-feature-dictionary.md`'s definitions, but it isn't
wired into the API response yet).

## What's NOT implemented

- **Permutation importance** — not computed. Would require holding out
  a validation set at inference time and shuffling one feature at a
  time, which isn't wired into the training or inference paths.
- **SHAP values** — not computed. `shap` is not a dependency of
  `ml_worker`. For tree models (`rf`/`gbm`) this would be the more
  rigorous choice over raw `feature_importances_`; for `logreg`, SHAP
  values reduce to (roughly) the coefficient × standardized-feature
  product already computed as the "contribution" above.
- **Local (per-prediction) explanation beyond the top-5 list** — no
  waterfall chart, no counterfactual analysis.
- **Historical examples with similar feature patterns** — this is the
  spec's "similar-pattern analysis" module, entirely deferred (no
  nearest-neighbor search implemented).
- **Signed contribution is only rigorous for linear models.**
  `TrainedModel.signed_contributions(x_row, names)` returns
  `coefficient * standardized_feature_value` for `logreg`/`ridge` —
  a mathematically correct decomposition of the linear score, split
  into `positive_contributors_json` / `negative_contributors_json` by
  sign. For `rf`/`gbm`, no signed decomposition is computed (would
  require SHAP); the prediction instead reports the top-5 features by
  unsigned importance in `positive_contributors` only, with an
  explicit warning in the response's `warnings` list:
  *"Tree-based model: factor magnitudes shown are unsigned importance,
  not signed positive/negative contribution."* Never infer a sign for
  a tree-model factor from its presence in `positive_contributors` —
  read the warning.

## What the AI agent may and may not do with this

**Not yet wired**: no agent tool exists to fetch an ML prediction. The
spec's `get_ml_prediction`-style tool would need to be added to
`services/api/app/agent/tools.py::ALLOWED_TOOLS` following the same
pattern as `calculate_signal` — return the stored `ml_predictions` row
verbatim, never let the LLM recompute or adjust probabilities. Until
that tool exists, the AI research agent has no path to ML predictions
at all (it can only discuss the rule-based signal, which is unchanged
from Phase 4/agent implementation).

When that tool is added, the same rule that governs `calculate_signal`
applies: the agent may **translate** the stored `contribution` values
into natural language ("relative strength over the last 20 sessions
was a positive contributor") but must **preserve the quantitative
values** and must **never compute a new probability, expected return,
or confidence** — those come only from the model artifact via the
worker's inference path.

## Causation disclaimer

Every contributor returned by the API — coefficient-based or
importance-based — describes an **association** the fitted model found
in historical data, not a causal mechanism. `docs/ml-limitations.md`
covers this in more depth; the practical implication for any UI or
agent text is: describe factors as "the model weighted X" or "X was
associated with", never "X caused" or "X will cause."
