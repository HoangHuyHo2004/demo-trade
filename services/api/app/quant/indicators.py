"""Pure-function technical indicators.

Every function takes a chronological list of floats (oldest → newest) and
returns a list of the same length, with a leading ``NaN`` window while
the indicator warms up. All formulas are documented so results are
reproducible in tests. No dependency on pandas — the whole suite is a
single-file dependency of the signal engine.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

NaN = float("nan")


def _isnan(x: float) -> bool:
    return x != x  # noqa: PLR0124 - explicit NaN check


def sma(values: Sequence[float], window: int) -> list[float]:
    """Simple moving average. First ``window-1`` outputs are NaN."""
    if window <= 0:
        raise ValueError("window must be > 0")
    n = len(values)
    out = [NaN] * n
    if n < window:
        return out
    s = sum(values[:window])
    out[window - 1] = s / window
    for i in range(window, n):
        s += values[i] - values[i - window]
        out[i] = s / window
    return out


def ema(values: Sequence[float], window: int) -> list[float]:
    """Exponential moving average using the Wilder-style seed:
    ``EMA[window-1] = SMA(values[0..window])`` then
    ``EMA[i] = (values[i] - EMA[i-1]) * alpha + EMA[i-1]`` with
    ``alpha = 2 / (window + 1)``.
    """
    if window <= 0:
        raise ValueError("window must be > 0")
    n = len(values)
    out = [NaN] * n
    if n < window:
        return out
    alpha = 2.0 / (window + 1.0)
    out[window - 1] = sum(values[:window]) / window
    for i in range(window, n):
        out[i] = (values[i] - out[i - 1]) * alpha + out[i - 1]
    return out


def macd(
    values: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float], list[float], list[float]]:
    """MACD line, signal line, histogram. Standard defaults 12/26/9."""
    if not (fast < slow):
        raise ValueError("fast must be < slow")
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    macd_line = [
        (a - b) if not (_isnan(a) or _isnan(b)) else NaN
        for a, b in zip(ema_fast, ema_slow, strict=True)
    ]
    # signal line is EMA of the MACD line, skipping the NaN prefix.
    trimmed = [x for x in macd_line if not _isnan(x)]
    sig_trim = ema(trimmed, signal)
    lead = len(macd_line) - len(trimmed)
    sig_line = [NaN] * lead + sig_trim
    hist = [
        (m - s) if not (_isnan(m) or _isnan(s)) else NaN
        for m, s in zip(macd_line, sig_line, strict=True)
    ]
    return macd_line, sig_line, hist


def rsi(values: Sequence[float], window: int = 14) -> list[float]:
    """Wilder RSI.

    ``avg_gain[t]`` and ``avg_loss[t]`` use Wilder smoothing after the
    initial simple-mean warm-up over the first ``window`` diffs.
    ``RSI = 100 - 100 / (1 + RS)`` where ``RS = avg_gain / avg_loss``.
    ``NaN`` returned when we can't yet form the moving average, or when
    ``avg_loss == 0`` at initialization (rare edge case).
    """
    n = len(values)
    out = [NaN] * n
    if n <= window:
        return out
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, n):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:window]) / window
    avg_loss = sum(losses[:window]) / window
    if avg_loss == 0 and avg_gain == 0:
        out[window] = 50.0
    elif avg_loss == 0:
        out[window] = 100.0
    else:
        rs = avg_gain / avg_loss
        out[window] = 100.0 - 100.0 / (1.0 + rs)
    for i in range(window + 1, n):
        g = gains[i - 1]
        loss = losses[i - 1]
        avg_gain = (avg_gain * (window - 1) + g) / window
        avg_loss = (avg_loss * (window - 1) + loss) / window
        if avg_loss == 0 and avg_gain == 0:
            out[i] = 50.0
        elif avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def atr(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    window: int = 14,
) -> list[float]:
    """Average True Range (Wilder).

    ``TR[t] = max(high-low, |high-close_prev|, |low-close_prev|)``,
    seeded with ``ATR[window] = mean(TR[1..window])`` then Wilder-smoothed.
    """
    n = len(close)
    if not (len(high) == len(low) == n):
        raise ValueError("high/low/close must be the same length")
    out = [NaN] * n
    if n <= window:
        return out
    tr = [NaN] * n
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    out[window] = sum(tr[1 : window + 1]) / window
    for i in range(window + 1, n):
        out[i] = (out[i - 1] * (window - 1) + tr[i]) / window
    return out


def realized_vol(closes: Sequence[float], window: int = 20, periods_per_year: int = 252) -> list[float]:
    """Annualized standard deviation of log returns over ``window``."""
    n = len(closes)
    out = [NaN] * n
    if n < window + 1:
        return out
    log_ret = [math.log(closes[i] / closes[i - 1]) for i in range(1, n)]
    # Rolling stdev of log_ret with a `window` size, aligned back to closes[i].
    for i in range(window, n):
        window_vals = log_ret[i - window : i]
        mean = sum(window_vals) / window
        var = sum((x - mean) ** 2 for x in window_vals) / (window - 1)
        out[i] = math.sqrt(var * periods_per_year)
    return out


def max_drawdown(equity: Sequence[float]) -> float:
    """Maximum peak-to-trough drawdown over an equity curve (as a
    non-negative fraction: 0.30 == 30% drawdown).
    """
    peak = -math.inf
    mdd = 0.0
    for v in equity:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > mdd:
                mdd = dd
    return mdd


def momentum(closes: Sequence[float], lookback: int) -> list[float]:
    """Simple point-to-point return over ``lookback`` bars."""
    n = len(closes)
    out = [NaN] * n
    for i in range(lookback, n):
        prev = closes[i - lookback]
        if prev:
            out[i] = closes[i] / prev - 1.0
    return out


def rolling_zscore(values: Sequence[float], window: int) -> list[float]:
    """Rolling z-score with ``window`` samples."""
    n = len(values)
    out = [NaN] * n
    if n < window:
        return out
    for i in range(window - 1, n):
        window_vals = values[i - window + 1 : i + 1]
        mean = sum(window_vals) / window
        var = sum((x - mean) ** 2 for x in window_vals) / (window - 1) if window > 1 else 0.0
        sd = math.sqrt(var) if var > 0 else 0.0
        out[i] = (values[i] - mean) / sd if sd > 0 else 0.0
    return out


def breakout_status(closes: Sequence[float], window: int = 55) -> list[str]:
    """Donchian-channel breakout state per bar.

    Returns one of: 'BREAKOUT_HIGH', 'BREAKDOWN_LOW', 'INSIDE', or ''
    while warming up.
    """
    n = len(closes)
    out: list[str] = [""] * n
    if n < window + 1:
        return out
    for i in range(window, n):
        prev = closes[i - window : i]
        hi = max(prev)
        lo = min(prev)
        c = closes[i]
        if c > hi:
            out[i] = "BREAKOUT_HIGH"
        elif c < lo:
            out[i] = "BREAKDOWN_LOW"
        else:
            out[i] = "INSIDE"
    return out


def relative_strength(closes: Sequence[float], benchmark_closes: Sequence[float], lookback: int) -> list[float]:
    """Asset momentum minus benchmark momentum over ``lookback`` bars.

    Both series must be aligned to the same timestamps. Where either side
    has NaN or a zero baseline, the output is NaN for that bar.
    """
    n = min(len(closes), len(benchmark_closes))
    a = momentum(closes[:n], lookback)
    b = momentum(benchmark_closes[:n], lookback)
    return [
        (x - y) if not (_isnan(x) or _isnan(y)) else NaN
        for x, y in zip(a, b, strict=True)
    ]


def last_finite(seq: Iterable[float]) -> float | None:
    """Return the last non-NaN value, or None if the sequence is empty/all NaN."""
    result: float | None = None
    for x in seq:
        if not _isnan(x):
            result = x
    return result
