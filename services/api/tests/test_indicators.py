"""Indicator library — fixed-fixture correctness tests.

Each check has either a hand-computed expected value or an analytical
property that must hold. Determinism means these numbers should never
drift under refactors.
"""
import math

import pytest

from app.quant.indicators import (
    atr,
    breakout_status,
    ema,
    macd,
    max_drawdown,
    momentum,
    realized_vol,
    relative_strength,
    rolling_zscore,
    rsi,
    sma,
)


def _isnan(x):
    return x != x  # noqa: PLR0124


# ---------- SMA ----------

def test_sma_basic():
    xs = [1, 2, 3, 4, 5]
    out = sma(xs, 3)
    assert _isnan(out[0]) and _isnan(out[1])
    assert out[2:] == pytest.approx([2.0, 3.0, 4.0])


def test_sma_window_larger_than_input_all_nan():
    out = sma([1.0, 2.0], 5)
    assert all(_isnan(x) for x in out)


# ---------- EMA ----------

def test_ema_seed_and_alpha():
    # window=3 → alpha = 2/(3+1) = 0.5
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    out = ema(xs, 3)
    # seed EMA[2] = mean(1,2,3) = 2.0
    assert out[2] == pytest.approx(2.0)
    # EMA[3] = (4 - 2.0)*0.5 + 2.0 = 3.0
    assert out[3] == pytest.approx(3.0)
    # EMA[4] = (5 - 3.0)*0.5 + 3.0 = 4.0
    assert out[4] == pytest.approx(4.0)


# ---------- RSI ----------

def test_rsi_all_up_moves_saturates_to_100():
    xs = list(range(1, 30))  # strictly increasing
    r = rsi(xs, 14)
    # After warmup all values should saturate at 100 (no losses)
    tail = [v for v in r[14:] if not _isnan(v)]
    assert tail and all(abs(v - 100.0) < 1e-9 for v in tail)


def test_rsi_flat_series_is_50():
    xs = [10.0] * 30
    r = rsi(xs, 14)
    tail = [v for v in r[14:] if not _isnan(v)]
    assert tail and all(abs(v - 50.0) < 1e-9 for v in tail)


# ---------- MACD ----------

def test_macd_shapes_and_convergence():
    xs = [float(i) for i in range(1, 60)]
    line, sig, hist = macd(xs, 12, 26, 9)
    assert len(line) == len(sig) == len(hist) == len(xs)
    # After enough bars, all three should be finite
    assert not _isnan(line[-1]) and not _isnan(sig[-1]) and not _isnan(hist[-1])
    # hist == line - signal, at every non-NaN point
    for a, b, h in zip(line, sig, hist, strict=True):
        if not (_isnan(a) or _isnan(b)):
            assert h == pytest.approx(a - b)


# ---------- ATR ----------

def test_atr_constant_range():
    # Every bar: high=101, low=99, close=100 → TR = 2 for i>=1 → ATR = 2 after warmup
    n = 30
    high = [101.0] * n
    low = [99.0] * n
    close = [100.0] * n
    a = atr(high, low, close, 14)
    assert not _isnan(a[14])
    assert a[14] == pytest.approx(2.0)
    assert a[-1] == pytest.approx(2.0)


# ---------- Realized vol ----------

def test_realized_vol_positive_for_random_walk():
    # Deterministic non-constant series
    xs = [100.0 * (1.01 if i % 2 == 0 else 0.99) ** i for i in range(1, 50)]
    v = realized_vol(xs, window=20)
    tail = [x for x in v if not _isnan(x)]
    assert tail and all(x > 0 for x in tail)


def test_realized_vol_zero_for_constant_series():
    xs = [100.0] * 40
    v = realized_vol(xs, window=20)
    assert v[-1] == pytest.approx(0.0, abs=1e-12)


# ---------- Max drawdown ----------

def test_max_drawdown_known_curve():
    # peak 100, trough 60 → 40% MDD
    curve = [80.0, 90.0, 100.0, 80.0, 60.0, 70.0, 90.0]
    assert max_drawdown(curve) == pytest.approx(0.4)


def test_max_drawdown_monotone_up_is_zero():
    assert max_drawdown([1.0, 2.0, 3.0, 5.0]) == 0.0


# ---------- Momentum ----------

def test_momentum_simple_return():
    xs = [10.0, 11.0, 12.0, 13.0]
    m = momentum(xs, 3)
    assert _isnan(m[0]) and _isnan(m[1]) and _isnan(m[2])
    assert m[3] == pytest.approx(0.3)


# ---------- Rolling z-score ----------

def test_rolling_zscore_constant_zero():
    xs = [5.0] * 10
    z = rolling_zscore(xs, 5)
    tail = [v for v in z if not _isnan(v)]
    assert tail and all(v == 0.0 for v in tail)


def test_rolling_zscore_last_high_value_positive():
    xs = [1.0] * 9 + [10.0]
    z = rolling_zscore(xs, 5)
    assert z[-1] > 0


# ---------- Breakout ----------

def test_breakout_status_marks_new_high():
    xs = list(range(1, 100))  # strictly increasing
    st = breakout_status(xs, window=55)
    # After warmup, every bar should be BREAKOUT_HIGH (new high)
    tail = [s for s in st[55:] if s]
    assert tail and all(s == "BREAKOUT_HIGH" for s in tail)


def test_breakout_status_marks_new_low():
    xs = list(range(100, 1, -1))
    st = breakout_status(xs, window=55)
    tail = [s for s in st[55:] if s]
    assert tail and all(s == "BREAKDOWN_LOW" for s in tail)


# ---------- Relative strength ----------

def test_relative_strength_positive_when_asset_outperforms():
    asset = [100 * (1.02 ** i) for i in range(20)]
    bench = [100 * (1.005 ** i) for i in range(20)]
    rs = relative_strength(asset, bench, lookback=10)
    tail = [v for v in rs if not _isnan(v)]
    assert tail and all(v > 0 for v in tail)


# ---------- Determinism ----------

def test_indicators_are_deterministic():
    xs = [math.sin(i / 3) + i * 0.1 for i in range(80)]
    a1 = sma(xs, 20); a2 = sma(xs, 20)
    b1 = ema(xs, 20); b2 = ema(xs, 20)
    assert a1 == a2 and b1 == b2
    c1 = rsi(xs, 14); c2 = rsi(xs, 14)
    assert c1 == c2
