"""Feature pipeline v1 — deterministic, pure functions on OHLCV.

Every feature here is a function of past bars ONLY. Any use of the
current bar's OHLC as an input into a feature intended for a "before
close" prediction is a leakage bug; tests in ``tests/test_ml_pipeline.py``
enforce this by comparing feature values with and without the last bar.

Input shape:
  ``build_features(closes, highs, lows, volumes, benchmark_closes)``
  where every list is chronological, oldest → newest, and all shapes
  match. The last bar is treated as the "current" observation; features
  are lagged appropriately.

Every returned feature is:
  * scalar (int or float),
  * finite or ``float('nan')``,
  * documented in ``docs/ml-feature-dictionary.md``.

The feature version is ``FEATURE_VERSION`` in ``app.ml.__init__``. Any
change to *what* is computed → new version.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from app.quant import indicators as ind

NaN = float("nan")


def _last(seq: Sequence[float]) -> float | None:
    """Last non-NaN value, or None if the sequence is empty / all NaN."""
    return ind.last_finite(seq)


def _safe_div(a: float | None, b: float | None) -> float:
    if a is None or b is None or b == 0 or not math.isfinite(a) or not math.isfinite(b):
        return NaN
    return a / b


def build_features(
    *,
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    volumes: Sequence[float],
    benchmark_closes: Sequence[float] | None = None,
) -> dict[str, float]:
    """Compute the v1 feature dict.

    Returns NaNs where the underlying window isn't warm yet. Downstream
    callers should either drop rows with NaN features (during training)
    or return ``INSUFFICIENT_DATA`` (during inference).
    """
    n = len(closes)
    out: dict[str, float] = {}

    # --- Returns (log + simple) ---
    if n >= 2 and closes[-2] > 0:
        out["ret_1d"] = math.log(closes[-1] / closes[-2])
    else:
        out["ret_1d"] = NaN

    for lag in (5, 10, 20, 60):
        if n > lag and closes[-lag - 1] > 0:
            out[f"ret_{lag}d"] = math.log(closes[-1] / closes[-lag - 1])
        else:
            out[f"ret_{lag}d"] = NaN

    # --- Trend / EMA relationships ---
    ema10 = _last(ind.ema(closes, 10))
    ema20 = _last(ind.ema(closes, 20))
    ema50 = _last(ind.ema(closes, 50))
    ema200 = _last(ind.ema(closes, 200))
    out["ema10_over_ema50"] = _safe_div(ema10, ema50)
    out["ema20_over_ema50"] = _safe_div(ema20, ema50)
    out["ema20_over_ema200"] = _safe_div(ema20, ema200)
    out["price_over_ema50"] = _safe_div(closes[-1], ema50)
    out["price_over_ema200"] = _safe_div(closes[-1], ema200)

    # MA slope (20-bar): ema20[-1] / ema20[-20] - 1, else NaN
    ema20_series = ind.ema(closes, 20)
    if len(ema20_series) >= 20 and math.isfinite(ema20_series[-1]) \
            and math.isfinite(ema20_series[-20]) and ema20_series[-20] > 0:
        out["ema20_slope_20"] = ema20_series[-1] / ema20_series[-20] - 1.0
    else:
        out["ema20_slope_20"] = NaN

    # Donchian breakout
    st = ind.breakout_status(closes, window=55)
    tag = st[-1] if st else ""
    out["breakout_hi_55"] = 1.0 if tag == "BREAKOUT_HIGH" else 0.0
    out["breakdown_lo_55"] = 1.0 if tag == "BREAKDOWN_LOW" else 0.0

    # --- Momentum ---
    out["rsi_14"] = _last(ind.rsi(closes, 14)) or NaN
    macd_line, macd_sig, macd_hist = ind.macd(closes, 12, 26, 9)
    last_hist = _last(macd_hist)
    if last_hist is not None and closes[-1] > 0:
        out["macd_hist_pct_price"] = last_hist / closes[-1]
    else:
        out["macd_hist_pct_price"] = NaN
    out["mom_20"] = _last(ind.momentum(closes, 20)) or NaN
    out["mom_60"] = _last(ind.momentum(closes, 60)) or NaN

    # --- Volatility ---
    atr = _last(ind.atr(list(highs), list(lows), list(closes), 14))
    if atr is not None and closes[-1] > 0:
        out["atr_pct_14"] = atr / closes[-1]
    else:
        out["atr_pct_14"] = NaN
    out["realized_vol_20"] = _last(ind.realized_vol(closes, 20)) or NaN
    out["realized_vol_60"] = _last(ind.realized_vol(closes, 60)) or NaN

    # Drawdown from recent peak
    recent = closes[-60:] if n >= 60 else closes
    out["mdd_60"] = ind.max_drawdown(recent)

    # Overnight-style gap proxy: |close[-1] - close[-2]| / atr
    if n >= 2 and atr and atr > 0:
        out["gap_over_atr"] = abs(closes[-1] - closes[-2]) / atr
    else:
        out["gap_over_atr"] = NaN

    # --- Volume ---
    if len(volumes) >= 20:
        vol_ma = sum(volumes[-20:]) / 20 if any(volumes[-20:]) else 0.0
        if vol_ma > 0:
            out["rel_volume_20"] = volumes[-1] / vol_ma
        else:
            out["rel_volume_20"] = NaN
        vz = _last(ind.rolling_zscore(list(volumes), 20))
        out["vol_z_20"] = vz if vz is not None else NaN
        # Volume-price divergence: sign of last return vs sign of vol z
        last_ret = out.get("ret_1d", NaN)
        if math.isfinite(last_ret) and vz is not None:
            out["vp_divergence"] = (
                1.0 if (last_ret > 0 and vz < 0) or (last_ret < 0 and vz > 0) else 0.0
            )
        else:
            out["vp_divergence"] = NaN
    else:
        out["rel_volume_20"] = NaN
        out["vol_z_20"] = NaN
        out["vp_divergence"] = NaN

    # --- Benchmark-relative ---
    if benchmark_closes is not None and len(benchmark_closes) == n:
        rs = _last(ind.relative_strength(list(closes), list(benchmark_closes), 20))
        out["rel_strength_20"] = rs if rs is not None else NaN
        bench_mom_20 = _last(ind.momentum(list(benchmark_closes), 20))
        out["bench_mom_20"] = bench_mom_20 if bench_mom_20 is not None else NaN
        # correlation of last 60 log returns
        if n >= 62:
            r_a = [
                math.log(closes[i] / closes[i - 1])
                for i in range(n - 60, n)
                if closes[i - 1] > 0
            ]
            r_b = [
                math.log(benchmark_closes[i] / benchmark_closes[i - 1])
                for i in range(n - 60, n)
                if benchmark_closes[i - 1] > 0
            ]
            m = min(len(r_a), len(r_b))
            out["corr_bench_60"] = _corr(r_a[-m:], r_b[-m:])
        else:
            out["corr_bench_60"] = NaN
    else:
        out["rel_strength_20"] = NaN
        out["bench_mom_20"] = NaN
        out["corr_bench_60"] = NaN

    return out


def feature_names() -> list[str]:
    """Return the canonical ordered feature name list.

    Determinism: this must match the keys ``build_features`` emits, in
    the same order, so trained-model coefficients line up with inference
    inputs. Any change → new ``FEATURE_VERSION``.
    """
    return [
        # Returns
        "ret_1d", "ret_5d", "ret_10d", "ret_20d", "ret_60d",
        # Trend
        "ema10_over_ema50", "ema20_over_ema50", "ema20_over_ema200",
        "price_over_ema50", "price_over_ema200",
        "ema20_slope_20",
        "breakout_hi_55", "breakdown_lo_55",
        # Momentum
        "rsi_14", "macd_hist_pct_price", "mom_20", "mom_60",
        # Volatility
        "atr_pct_14", "realized_vol_20", "realized_vol_60",
        "mdd_60", "gap_over_atr",
        # Volume
        "rel_volume_20", "vol_z_20", "vp_divergence",
        # Benchmark
        "rel_strength_20", "bench_mom_20", "corr_bench_60",
    ]


def _corr(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return NaN
    ma = sum(a) / n
    mb = sum(b) / n
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n)) / (n - 1)
    va = sum((x - ma) ** 2 for x in a) / (n - 1)
    vb = sum((x - mb) ** 2 for x in b) / (n - 1)
    sa = math.sqrt(va) if va > 0 else 0.0
    sb = math.sqrt(vb) if vb > 0 else 0.0
    if sa == 0 or sb == 0:
        return NaN
    return cov / (sa * sb)
