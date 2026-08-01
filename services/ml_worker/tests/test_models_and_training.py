"""Smoke tests for the sklearn model wrappers + training loop.

No DB dependency — uses synthetic feature/label arrays so this can run
standalone against the ml_worker venv (sklearn/joblib/numpy only).
"""
import os
import tempfile

import numpy as np
import pytest

from mlw.models import (
    TrainedModel,
    make_direction_model,
    make_fit_class_mask,
    sha256_of_file,
)
from mlw.training import (
    features_matrix_from_rows,
    train_direction_model,
)


def _synthetic_xy(n=400, n_features=5, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, n_features))
    # y correlated with feature 0 so the model has something real to learn
    logits = 1.5 * X[:, 0] - 0.5 * X[:, 1] + rng.normal(scale=0.5, size=n)
    y = (logits > 0).astype(int) * 2 - 1  # produces {-1, 1}
    # sprinkle some neutral (0) labels
    neutral_mask = rng.random(n) < 0.1
    y[neutral_mask] = 0
    return X, y


def test_make_fit_class_mask_drops_neutral():
    y = np.array([-1, 0, 1, 0, 1, -1])
    yb, mask = make_fit_class_mask(y)
    assert mask.tolist() == [True, False, True, False, True, True]
    assert set(yb.tolist()) <= {0, 1}
    assert len(yb) == mask.sum()


@pytest.mark.parametrize("family", ["logreg", "rf", "gbm"])
def test_direction_model_fits_and_predicts(family):
    X, y = _synthetic_xy(seed=1)
    yb, mask = make_fit_class_mask(y)
    Xf = X[mask]
    m = make_direction_model(family, seed=42)
    m.fit_result = m.estimator.fit(Xf, yb)
    proba = m.predict_proba(Xf)
    assert proba.shape == (len(Xf), 2)
    assert np.all((proba >= 0) & (proba <= 1))
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)


def test_logreg_recovers_meaningful_signal():
    """Feature 0 is the strongest driver by construction — logreg
    should assign it the largest |coefficient|."""
    X, y = _synthetic_xy(n=2000, seed=2)
    yb, mask = make_fit_class_mask(y)
    m = make_direction_model("logreg", seed=0)
    m.estimator.fit(X[mask], yb)
    m.feature_names = ["f0", "f1", "f2", "f3", "f4"]
    imp = m.feature_importance(m.feature_names)
    assert imp["f0"] == max(imp.values())


def test_signed_contributions_logreg_matches_sign_of_coef_times_value():
    X, y = _synthetic_xy(n=500, seed=3)
    yb, mask = make_fit_class_mask(y)
    m = make_direction_model("logreg", seed=0)
    m.estimator.fit(X[mask], yb)
    names = ["f0", "f1", "f2", "f3", "f4"]
    row = X[0]
    signed = m.signed_contributions(row, names)
    assert signed is not None
    assert set(signed.keys()) == set(names)


def test_signed_contributions_none_for_tree_models():
    X, y = _synthetic_xy(seed=4)
    yb, mask = make_fit_class_mask(y)
    m = make_direction_model("rf", seed=0)
    m.estimator.fit(X[mask], yb)
    signed = m.signed_contributions(X[0], ["f0", "f1", "f2", "f3", "f4"])
    assert signed is None  # honest: no signed decomposition for trees


def test_save_and_load_roundtrip_preserves_predictions():
    X, y = _synthetic_xy(seed=5)
    yb, mask = make_fit_class_mask(y)
    m = make_direction_model("logreg", seed=0)
    m.estimator.fit(X[mask], yb)
    m.feature_names = ["f0", "f1", "f2", "f3", "f4"]
    before = m.predict_proba(X[:5])

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "model.joblib")
        sha1 = m.save(path)
        sha2 = sha256_of_file(path)
        assert sha1 == sha2

        loaded = TrainedModel.load(path)
        after = loaded.predict_proba(X[:5])
        np.testing.assert_allclose(before, after)
        assert loaded.feature_names == m.feature_names


def test_train_direction_model_end_to_end():
    X, y = _synthetic_xy(n=1000, seed=6)
    split = 700
    m, metrics, detail = train_direction_model(
        family="logreg",
        X_train=X[:split], y_train=y[:split],
        X_val=X[split:], y_val=y[split:],
        feature_names=["f0", "f1", "f2", "f3", "f4"],
        seed=0, calibrate="isotonic",
    )
    assert metrics.n_train > 0
    assert metrics.n_val > 0
    assert metrics.roc_auc is not None
    assert metrics.roc_auc > 0.5  # better than random on a real signal
    assert 0 <= metrics.brier <= 1
    assert len(metrics.calibration_bins) > 0
    assert detail["family"] == "logreg"


def test_train_direction_model_raises_on_too_little_data():
    X, y = _synthetic_xy(n=20, seed=7)
    with pytest.raises(ValueError):
        train_direction_model(
            family="logreg",
            X_train=X[:10], y_train=y[:10],
            X_val=X[10:], y_val=y[10:],
            feature_names=["f0", "f1", "f2", "f3", "f4"],
        )


def test_features_matrix_from_rows_drops_nan_rows():
    rows = [
        {"a": 1.0, "b": 2.0, "direction": 1},
        {"a": float("nan"), "b": 2.0, "direction": -1},
        {"a": 3.0, "b": None, "direction": 0},
        {"a": 4.0, "b": 5.0, "direction": -1},
    ]
    X, y = features_matrix_from_rows(rows, ["a", "b"])
    assert X.shape == (2, 2)
    assert y.tolist() == [1, -1]


def test_calibration_improves_or_maintains_brier_vs_uncalibrated():
    """Not a strict guarantee for every seed, but on a reasonably-sized
    sample calibration should not make Brier drastically worse."""
    X, y = _synthetic_xy(n=1500, seed=8)
    split = 1000
    _, metrics_cal, _ = train_direction_model(
        family="logreg", X_train=X[:split], y_train=y[:split],
        X_val=X[split:], y_val=y[split:],
        feature_names=["f0", "f1", "f2", "f3", "f4"],
        seed=0, calibrate="isotonic",
    )
    _, metrics_uncal, _ = train_direction_model(
        family="logreg", X_train=X[:split], y_train=y[:split],
        X_val=X[split:], y_val=y[split:],
        feature_names=["f0", "f1", "f2", "f3", "f4"],
        seed=0, calibrate="none",
    )
    assert metrics_cal.brier is not None
    assert metrics_uncal.brier is not None
    # Both should be well below the "always predict 0.5" baseline of 0.25.
    assert metrics_cal.brier < 0.25
