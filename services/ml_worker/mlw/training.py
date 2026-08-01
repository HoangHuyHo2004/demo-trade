"""Training runner.

One call to ``train_direction_model`` walks a single fold: fit on
train, calibrate probabilities on val, evaluate on val (test if
present). We deliberately keep a single fold per training run to
match the spec's ``ml_training_runs`` row-per-attempt model — the
walk-forward loop is implemented by the API/task layer that calls
``train_direction_model`` once per fold and records N rows.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)

from mlw.models import TrainedModel, make_direction_model, make_fit_class_mask


@dataclass
class DirectionMetrics:
    n_train: int
    n_val: int
    n_pos_train: int
    n_pos_val: int
    roc_auc: float | None
    pr_auc: float | None
    log_loss: float | None
    brier: float | None
    accuracy: float | None
    baseline_positive_rate: float | None
    calibration_bins: list[dict[str, float]]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def train_direction_model(
    *,
    family: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    feature_names: list[str],
    seed: int = 0,
    calibrate: str = "isotonic",   # "isotonic" | "sigmoid" | "none"
) -> tuple[TrainedModel, DirectionMetrics, dict[str, Any]]:
    """Fit → calibrate → evaluate. Returns (model, metrics, log-detail)."""
    t0 = time.perf_counter()
    yb_train, mask_train = make_fit_class_mask(y_train)
    yb_val, mask_val = make_fit_class_mask(y_val)
    Xt = X_train[mask_train]
    Xv = X_val[mask_val]

    m = make_direction_model(family, seed=seed)
    m.feature_names = list(feature_names)
    if len(Xt) < 30 or len(np.unique(yb_train)) < 2:
        raise ValueError(
            f"insufficient training data: n={len(Xt)}, classes={np.unique(yb_train)}"
        )
    m.estimator.fit(Xt, yb_train)

    # Calibrate on validation. Wrap the FITTED base estimator so
    # calibration only sees validation data — never train, never test.
    #
    # scikit-learn >=1.6 removed CalibratedClassifierCV(cv="prefit") in
    # favor of wrapping the fitted estimator in sklearn.frozen.FrozenEstimator.
    # We support both so this runs against whichever sklearn is pinned.
    if calibrate in ("isotonic", "sigmoid") and len(Xv) >= 30:
        try:
            from sklearn.frozen import FrozenEstimator
            cal = CalibratedClassifierCV(FrozenEstimator(m.estimator), method=calibrate)
        except ImportError:
            cal = CalibratedClassifierCV(m.estimator, method=calibrate, cv="prefit")
        cal.fit(Xv, yb_val)
        m.estimator = cal

    # Evaluate on val
    prob_val = m.predict_proba(Xv)[:, 1] if len(Xv) > 0 else np.array([])
    metrics = DirectionMetrics(
        n_train=int(len(Xt)),
        n_val=int(len(Xv)),
        n_pos_train=int(yb_train.sum()),
        n_pos_val=int(yb_val.sum()),
        roc_auc=_safe(lambda: float(roc_auc_score(yb_val, prob_val))),
        pr_auc=_safe(lambda: float(average_precision_score(yb_val, prob_val))),
        log_loss=_safe(lambda: float(log_loss(yb_val, prob_val, labels=[0, 1]))),
        brier=_safe(lambda: float(brier_score_loss(yb_val, prob_val))),
        accuracy=_safe(
            lambda: float(((prob_val >= 0.5).astype(int) == yb_val).mean())
        ),
        baseline_positive_rate=float(yb_val.mean()) if len(yb_val) else None,
        calibration_bins=_reliability_bins(yb_val, prob_val, bins=10),
    )

    detail = {
        "family": family,
        "seed": seed,
        "calibrate": calibrate,
        "fit_wallclock_ms": int((time.perf_counter() - t0) * 1000),
        "trained_at": datetime.now(UTC).isoformat(),
    }
    return m, metrics, detail


def _safe(fn):
    try:
        v = fn()
        return v if v == v else None   # reject NaN
    except Exception:
        return None


def _reliability_bins(y_true, y_prob, bins: int = 10) -> list[dict[str, float]]:
    """Reliability diagram bins for a calibration curve."""
    if len(y_true) == 0:
        return []
    edges = np.linspace(0.0, 1.0, bins + 1)
    out = []
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        if i == bins - 1:
            mask = (y_prob >= lo) & (y_prob <= hi)
        else:
            mask = (y_prob >= lo) & (y_prob < hi)
        n = int(mask.sum())
        if n == 0:
            continue
        out.append({
            "bucket_low": float(lo),
            "bucket_high": float(hi),
            "n": n,
            "mean_pred": float(y_prob[mask].mean()),
            "actual_positive_rate": float(y_true[mask].mean()),
        })
    return out


def features_matrix_from_rows(
    rows: list[dict], feature_names: list[str], target_key: str = "direction",
) -> tuple[np.ndarray, np.ndarray]:
    """Extract (X, y) from a dataset row list (see app.ml.datasets)."""
    xs, ys = [], []
    for r in rows:
        y = r.get(target_key)
        if y is None:
            continue
        feats = [r.get(n) for n in feature_names]
        if any(f is None or (isinstance(f, float) and f != f) for f in feats):
            continue
        xs.append(feats)
        ys.append(y)
    if not xs:
        return np.empty((0, len(feature_names))), np.empty((0,), dtype=int)
    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=int)


def to_json_dict(obj: DirectionMetrics) -> str:
    return json.dumps(obj.as_dict(), sort_keys=True, default=str)
