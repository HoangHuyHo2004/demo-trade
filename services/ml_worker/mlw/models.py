"""Baseline model wrappers.

All wrappers expose the same tiny interface so the training loop is
independent of which family it's training:

    m = MakeModel(family)
    m.fit(X_train, y_train)
    proba = m.predict_proba(X)   # (n, 2) for direction; not applicable for regression
    yhat  = m.predict(X)         # class labels (direction) or values (regression)
    imp   = m.feature_importance(feature_names)  # dict[name, float]
    m.save(path)
    m.load(path)

We deliberately keep model complexity modest for Phase 1 — logistic /
ridge / random-forest / gradient-boosted. Advanced models (xgboost /
lightgbm / neural) are Phase 5 per spec.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class TrainedModel:
    family: str            # "logreg" | "ridge" | "rf" | "gbm"
    task: str              # "direction" | "regression"
    estimator: object      # sklearn pipeline or estimator
    feature_names: list[str] = field(default_factory=list)
    seed: int = 0

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if not hasattr(self.estimator, "predict_proba"):
            raise RuntimeError(f"{self.family} does not support predict_proba")
        return self.estimator.predict_proba(x)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return self.estimator.predict(x)

    def feature_importance(self, names: list[str]) -> dict[str, float]:
        """Best-effort importance. Coefficients for linear, tree-derived
        importance for RF/GBM. Not calibrated to a common scale. These
        are UNSIGNED magnitudes — use ``signed_contributions`` when you
        need to know direction (positive vs negative pull).
        """
        est = _terminal_estimator(self.estimator)
        if hasattr(est, "feature_importances_"):
            vals = est.feature_importances_
        elif hasattr(est, "coef_"):
            c = np.asarray(est.coef_).ravel()
            vals = np.abs(c) / (np.abs(c).sum() or 1.0)
        else:
            return {}
        return {n: float(v) for n, v in zip(names, vals, strict=False)}

    def signed_contributions(
        self, x_row: np.ndarray, names: list[str],
    ) -> dict[str, float] | None:
        """Signed per-feature contribution for ONE prediction row.

        Only available for linear models (logreg/ridge), where
        ``contribution = coefficient * standardized_feature_value`` is a
        well-defined, correctly-signed decomposition of the model's
        linear score. Returns ``None`` for tree-based models (rf/gbm) —
        a rigorous signed decomposition for trees requires SHAP, which
        is not a dependency here (see docs/ml-explainability.md).
        Callers must not fabricate a sign for tree models.
        """
        est = _terminal_estimator(self.estimator)
        if not hasattr(est, "coef_"):
            return None
        coefs = np.asarray(est.coef_).ravel()
        xv = x_row
        if isinstance(self.estimator, Pipeline):
            steps = dict(self.estimator.steps)
            scaler = steps.get("scaler")
            if scaler is not None:
                xv = scaler.transform(x_row.reshape(1, -1))[0]
        return {n: float(coefs[i] * xv[i]) for i, n in enumerate(names)}

    def save(self, path: str) -> str:
        joblib.dump({
            "family": self.family,
            "task": self.task,
            "estimator": self.estimator,
            "feature_names": self.feature_names,
            "seed": self.seed,
        }, path, compress=3)
        return sha256_of_file(path)

    @classmethod
    def load(cls, path: str) -> TrainedModel:
        obj = joblib.load(path)
        return cls(**obj)


def make_direction_model(family: str, *, seed: int = 0) -> TrainedModel:
    """Return an untrained direction (classification) model."""
    if family == "logreg":
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                C=1.0, max_iter=500, solver="lbfgs",
                class_weight="balanced", random_state=seed,
            )),
        ])
    elif family == "rf":
        pipe = Pipeline([
            ("clf", RandomForestClassifier(
                n_estimators=200, max_depth=6, min_samples_leaf=20,
                class_weight="balanced_subsample",
                n_jobs=1, random_state=seed,
            )),
        ])
    elif family == "gbm":
        pipe = Pipeline([
            ("clf", GradientBoostingClassifier(
                n_estimators=200, max_depth=3, learning_rate=0.05,
                subsample=0.8, random_state=seed,
            )),
        ])
    else:
        raise ValueError(f"unknown direction family: {family!r}")
    return TrainedModel(family=family, task="direction", estimator=pipe, seed=seed)


def make_regression_model(family: str, *, seed: int = 0) -> TrainedModel:
    if family == "ridge":
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("reg", Ridge(alpha=1.0, random_state=seed)),
        ])
    else:
        raise ValueError(f"unknown regression family: {family!r}")
    return TrainedModel(family=family, task="regression", estimator=pipe, seed=seed)


def _terminal_estimator(pipe_or_est):
    if isinstance(pipe_or_est, Pipeline):
        return pipe_or_est.steps[-1][1]
    return pipe_or_est


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_fit_class_mask(y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Binary-ize a {-1, 0, 1} direction label into {0, 1} + a mask that
    drops the neutral class. Direction models are trained to predict
    'positive return after costs' vs 'negative return after costs'; the
    NEUTRAL zone is intentionally excluded to avoid teaching the model
    to trade in flat regimes."""
    mask = y != 0
    yb = (y[mask] > 0).astype(int)
    return yb, mask
