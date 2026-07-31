"""Rule-based signal ensemble (``ensemble-v1``).

Design goals:
  * Explainable — every score contribution is a named factor.
  * Deterministic — same input → same output.
  * No lookahead — assumes the caller filtered to ``available_at <= as_of``.
  * Modest — the model is intentionally conservative; low data quality
    or contradictory factors push confidence down or trigger
    INSUFFICIENT_DATA at the engine level.

Score buckets (per weight):
  * Trend  0.30  (EMA20 vs EMA60, MA-slope, MACD histogram)
  * Momentum  0.25 (RSI, 20d + 60d return)
  * Volatility  0.15 (ATR% percentile, drawdown warning)
  * Volume  0.15 (rvol z-score, abnormal-volume flag)
  * Benchmark  0.15 (relative strength vs market benchmark)

Each factor produces a signed contribution in [-1, 1]. Weighted sum is
clamped to [-1, 1] then scaled to [-100, 100].
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.quant import indicators as ind
from app.quant.models_base import (
    FactorContribution,
    ModelOutput,
    SignalInput,
    SignalModel,
)

_WEIGHTS = {
    "trend": 0.30,
    "momentum": 0.25,
    "volatility": 0.15,
    "volume": 0.15,
    "benchmark": 0.15,
}

# Minimum bars required to compute the full factor set. Below this we
# still produce a score, but data_quality is depressed and downstream
# code can decide to abstain.
_MIN_BARS = 90


@dataclass(frozen=True)
class EnsembleParams:
    ema_fast: int = 20
    ema_slow: int = 60
    rsi_window: int = 14
    atr_window: int = 14
    momentum_short: int = 20
    momentum_long: int = 60
    volume_z_window: int = 20
    rs_lookback: int = 20
    breakout_window: int = 55


class RuleBasedEnsemble(SignalModel):
    code = "ensemble-v1"
    family = "ensemble"
    description = (
        "Explainable rule-based ensemble: trend (EMA cross + MACD hist), "
        "momentum (RSI + 20/60d return), volatility (ATR%, drawdown), "
        "volume (relative-volume z-score), and benchmark-relative strength."
    )

    def __init__(self, params: EnsembleParams | None = None) -> None:
        self.params = params or EnsembleParams()

    def compute(self, si: SignalInput, *, horizon: str) -> ModelOutput:
        p = self.params
        n = len(si.close)

        contributions: list[FactorContribution] = []
        warnings: list[str] = []
        contradictions: list[str] = []

        # ---- Trend factors ----
        if n >= p.ema_slow:
            ema_fast = ind.ema(si.close, p.ema_fast)[-1]
            ema_slow = ind.ema(si.close, p.ema_slow)[-1]
            if _fin(ema_fast) and _fin(ema_slow) and ema_slow > 0:
                gap = (ema_fast - ema_slow) / ema_slow
                # scale: ±5% gap saturates
                trend_score = _clip(gap / 0.05, -1.0, 1.0)
                contributions.append(FactorContribution(
                    code="ema_cross",
                    label=f"EMA{p.ema_fast} vs EMA{p.ema_slow}",
                    category="trend",
                    contribution=trend_score,
                    detail=f"gap={gap:+.2%}",
                ))
        # MACD histogram
        macd_line, macd_sig, macd_hist = ind.macd(si.close, 12, 26, 9)
        last_hist = ind.last_finite(macd_hist)
        if last_hist is not None and si.close[-1] > 0:
            # scale by 1% of price → saturated
            macd_score = _clip(last_hist / (0.01 * si.close[-1]), -1.0, 1.0)
            contributions.append(FactorContribution(
                code="macd_hist",
                label="MACD histogram",
                category="trend",
                contribution=macd_score,
                detail=f"hist={last_hist:+.4f}",
            ))

        # ---- Momentum ----
        rsi_series = ind.rsi(si.close, p.rsi_window)
        rsi_last = ind.last_finite(rsi_series)
        if rsi_last is not None:
            # 50=neutral; ±25 from 50 saturates to ±1
            rsi_score = _clip((rsi_last - 50.0) / 25.0, -1.0, 1.0)
            contributions.append(FactorContribution(
                code="rsi",
                label=f"RSI({p.rsi_window})",
                category="momentum",
                contribution=rsi_score,
                detail=f"rsi={rsi_last:.1f}",
            ))
            if rsi_last >= 80:
                contradictions.append("RSI shows overbought conditions; upside likely limited")
            elif rsi_last <= 20:
                contradictions.append("RSI shows oversold conditions; further downside possible short-term")

        m20 = ind.last_finite(ind.momentum(si.close, p.momentum_short))
        m60 = ind.last_finite(ind.momentum(si.close, p.momentum_long))
        if m20 is not None:
            contributions.append(FactorContribution(
                code=f"mom_{p.momentum_short}d",
                label=f"{p.momentum_short}-bar return",
                category="momentum",
                contribution=_clip(m20 / 0.10, -1.0, 1.0),  # ±10% saturates
                detail=f"{m20:+.2%}",
            ))
        if m60 is not None:
            contributions.append(FactorContribution(
                code=f"mom_{p.momentum_long}d",
                label=f"{p.momentum_long}-bar return",
                category="momentum",
                contribution=_clip(m60 / 0.25, -1.0, 1.0),  # ±25% saturates
                detail=f"{m60:+.2%}",
            ))

        # ---- Volatility ----
        atr_series = ind.atr(si.high, si.low, si.close, p.atr_window)
        atr_last = ind.last_finite(atr_series)
        if atr_last is not None and si.close[-1] > 0:
            atr_pct = atr_last / si.close[-1]
            # High vol is *negative* for a long swing signal.
            vol_score = _clip(-(atr_pct - 0.02) / 0.05, -1.0, 1.0)
            contributions.append(FactorContribution(
                code="atr_pct",
                label=f"ATR%({p.atr_window})",
                category="volatility",
                contribution=vol_score,
                detail=f"atr%={atr_pct:.2%}",
            ))
            if atr_pct > 0.10:
                warnings.append(f"Realized volatility is high (ATR% {atr_pct:.1%}); size positions accordingly")

        # Rolling drawdown from recent peak
        recent = si.close[-60:] if n >= 60 else si.close
        mdd = ind.max_drawdown(recent)
        if mdd > 0.20:
            contributions.append(FactorContribution(
                code="drawdown_60",
                label="60-bar peak drawdown",
                category="volatility",
                contribution=-_clip(mdd / 0.5, 0.0, 1.0),  # deep DD → negative
                detail=f"{mdd:.1%}",
            ))

        # ---- Volume ----
        if len(si.volume) >= p.volume_z_window:
            vol_z = ind.last_finite(ind.rolling_zscore(si.volume, p.volume_z_window))
            if vol_z is not None:
                # Direction depends on last-bar return sign: strong volume in
                # the direction of the move confirms it.
                last_ret_sign = 0.0
                if n >= 2 and si.close[-2] > 0:
                    last_ret = si.close[-1] / si.close[-2] - 1.0
                    if abs(last_ret) > 1e-6:
                        last_ret_sign = 1.0 if last_ret > 0 else -1.0
                # ±2 std → saturates
                magnitude = _clip(abs(vol_z) / 2.0, 0.0, 1.0)
                vol_contrib = magnitude * last_ret_sign * (1.0 if vol_z > 0 else 0.3)
                contributions.append(FactorContribution(
                    code="volume_z",
                    label=f"Volume z-score({p.volume_z_window})",
                    category="volume",
                    contribution=vol_contrib,
                    detail=f"z={vol_z:+.2f}",
                ))
                if vol_z > 3:
                    warnings.append("Abnormally high volume — investigate news / catalyst")

        # ---- Benchmark relative strength ----
        if si.benchmark_close is not None and len(si.benchmark_close) == n:
            rs = ind.last_finite(
                ind.relative_strength(si.close, si.benchmark_close, p.rs_lookback)
            )
            if rs is not None:
                contributions.append(FactorContribution(
                    code="rel_strength",
                    label=f"vs {si.benchmark_symbol or 'benchmark'} ({p.rs_lookback} bars)",
                    category="benchmark",
                    contribution=_clip(rs / 0.10, -1.0, 1.0),
                    detail=f"{rs:+.2%}",
                ))

        # ---- Regime (asset-level) ----
        # Simple: EMA20 vs EMA60 slope on the last 20 bars
        ema20 = ind.ema(si.close, 20)
        regime = "NEUTRAL"
        if _fin(ema20[-1]) and n >= 40 and _fin(ema20[-20]):
            slope = (ema20[-1] - ema20[-20]) / ema20[-20]
            if slope > 0.03:
                regime = "BULL"
            elif slope < -0.03:
                regime = "BEAR"

        # ---- Data-quality score ----
        # 1.0 when we have >= _MIN_BARS bars and every category contributed.
        cats_hit = {c.category for c in contributions}
        cats_ok = len(cats_hit & _WEIGHTS.keys()) / len(_WEIGHTS)
        len_ok = min(1.0, n / _MIN_BARS)
        data_quality = round(0.5 * cats_ok + 0.5 * len_ok, 3)

        # ---- Aggregate ----
        # Per-category mean contribution × category weight
        by_cat: dict[str, list[float]] = {k: [] for k in _WEIGHTS}
        for c in contributions:
            if c.category in by_cat:
                by_cat[c.category].append(c.contribution)
        weighted = 0.0
        total_w = 0.0
        for cat, values in by_cat.items():
            if values:
                weighted += (sum(values) / len(values)) * _WEIGHTS[cat]
                total_w += _WEIGHTS[cat]
        if total_w > 0:
            score = weighted / total_w  # normalize by covered weight
        else:
            score = 0.0
        score_100 = _clip(score, -1.0, 1.0) * 100.0

        positive = sorted([c for c in contributions if c.contribution > 0],
                          key=lambda c: -c.contribution)
        negative = sorted([c for c in contributions if c.contribution < 0],
                          key=lambda c: c.contribution)

        # ---- Reference levels (only when defensible) ----
        entry_zone: tuple[float, float] | None = None
        invalidation: float | None = None
        take_profit: list[float] = []
        if score_100 > 20 and atr_last is not None and n >= 20:
            close = si.close[-1]
            # 1 ATR entry band around last close
            entry_zone = (close - atr_last, close + atr_last * 0.5)
            invalidation = min(close - 2.0 * atr_last, min(si.low[-20:]))
            take_profit = [close + 2.0 * atr_last, close + 4.0 * atr_last]

        return ModelOutput(
            score=score_100,
            factors=contributions,
            regime=regime,
            data_quality=data_quality,
            liquidity_warnings=warnings,
            contradictions=contradictions,
            positive_factors=positive,
            negative_factors=negative,
            entry_zone=entry_zone,
            invalidation=invalidation,
            take_profit=take_profit,
        )


def _fin(x: float) -> bool:
    return isinstance(x, float) and math.isfinite(x)


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
