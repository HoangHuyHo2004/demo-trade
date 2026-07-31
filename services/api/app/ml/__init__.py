"""Machine-learning subsystem (spec §ML Phase 1).

Pipeline is deliberately pure-Python/NumPy so it can run inside the api
service for inference-side helpers and inside services/ml_worker for
training. Heavy deps (scikit-learn, joblib, xgboost/lightgbm) live in
ml_worker only — see ``services/ml_worker/pyproject.toml``.

Versioning: every artifact this subsystem produces carries a version
string. The current pipeline versions are recorded here so a downstream
reader knows what code produced a given feature/target/dataset row.
"""

FEATURE_VERSION = "features-v1"
TARGET_VERSION = "targets-v1"
UNIVERSE_VERSION = "universe-v1"
