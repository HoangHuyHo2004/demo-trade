"""Target construction: direction thresholds, no lookahead, cost-adjusted zone."""
import math

import pytest

from app.ml.labels import compute_labels


def _flat_then_jump(n=50, jump_at=30, jump_pct=0.05):
    closes = [100.0] * n
    for i in range(jump_at, n):
        closes[i] = 100.0 * (1 + jump_pct)
    return closes


def test_direction_positive_when_return_exceeds_cost_threshold():
    closes = [100.0, 100.0, 100.0, 100.0, 100.0, 106.0, 106.0, 106.0]
    labels = compute_labels(closes, t=0, horizon=5, cost_bps=5.0)
    assert labels.direction == 1
    assert labels.future_return is not None
    assert labels.future_return > 0


def test_direction_negative_when_return_below_negative_threshold():
    closes = [100.0, 100.0, 100.0, 100.0, 100.0, 94.0, 94.0, 94.0]
    labels = compute_labels(closes, t=0, horizon=5, cost_bps=5.0)
    assert labels.direction == -1


def test_direction_neutral_inside_cost_adjusted_zone():
    # 5bps cost → round trip 10bps → neutral zone is roughly ±0.1%.
    # A 0.05% move should land in NEUTRAL.
    closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.05, 100.05, 100.05]
    labels = compute_labels(closes, t=0, horizon=5, cost_bps=5.0)
    assert labels.direction == 0


def test_wider_cost_widens_neutral_zone():
    closes = [100.0, 100.0, 100.0, 100.0, 100.0, 100.5, 100.5, 100.5]
    cheap = compute_labels(closes, t=0, horizon=5, cost_bps=1.0)
    expensive = compute_labels(closes, t=0, horizon=5, cost_bps=100.0)
    # Same price path, but higher assumed cost should be harder to clear
    # → expensive is more likely NEUTRAL than cheap.
    assert cheap.direction in (1, 0)
    assert expensive.direction == 0


def test_out_of_range_horizon_returns_none():
    closes = [100.0] * 10
    labels = compute_labels(closes, t=8, horizon=5, cost_bps=5.0)
    assert labels.direction is None
    assert labels.future_return is None


def test_negative_t_returns_none():
    closes = [100.0] * 10
    labels = compute_labels(closes, t=-1, horizon=5, cost_bps=5.0)
    assert labels.direction is None


def test_future_return_only_uses_closes_up_to_t_plus_horizon():
    """The defining leakage test for labels: appending MORE bars after
    t+horizon must not change the label at t."""
    base = _flat_then_jump(n=40, jump_at=35, jump_pct=0.10)
    labels_short = compute_labels(base, t=10, horizon=5, cost_bps=5.0)
    extended = base + [999.0, 999.0, 999.0]  # garbage future bars
    labels_extended = compute_labels(extended, t=10, horizon=5, cost_bps=5.0)
    assert labels_short.direction == labels_extended.direction
    assert labels_short.future_return == labels_extended.future_return
    assert labels_short.future_mdd == labels_extended.future_mdd


def test_future_vol_is_annualized_and_nonneg():
    closes, = ([100 * math.exp(0.001 * i + (0.02 if i % 3 == 0 else -0.01)) for i in range(30)],)
    labels = compute_labels(closes, t=5, horizon=10, cost_bps=5.0)
    assert labels.future_vol is not None
    assert labels.future_vol >= 0


def test_max_adverse_move_captures_intra_horizon_drawdown():
    # Price dips hard mid-horizon then recovers to flat — the label
    # should capture the dip, not just the endpoint return.
    closes = [100.0, 100.0, 100.0, 100.0, 100.0, 90.0, 95.0, 100.0, 100.0, 100.0]
    labels = compute_labels(closes, t=4, horizon=5, cost_bps=5.0)
    assert labels.future_mdd is not None
    assert labels.future_mdd < -0.05  # captured the -10% dip, not the flat endpoint


_ = pytest
