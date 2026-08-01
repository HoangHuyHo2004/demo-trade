"""Target construction (spec §Target construction).

For each observation at time t and horizon H bars:

  * direction_label(t, H, cost_bps): 1 / 0 / -1 based on whether the
    future H-bar return exceeds ±(2 * cost_bps) after costs (both sides).
    Neutral zone widens with cost so we don't label microstructure noise
    as a trade opportunity.
  * regression_target(t, H): future log return over H bars.
  * volatility_target(t, H): realized log-return stdev over the H bars.
  * drawdown_target(t, H): maximum adverse move (negative fraction) over
    the H bars.

Every label uses the CLOSE at t and the CLOSE at t+H (or the intermediate
closes for path-dependent targets). No use of information beyond t+H.

Version: TARGET_VERSION in ``app.ml.__init__``.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class LabelSet:
    direction: int | None      # -1 | 0 | 1
    future_return: float | None
    future_vol: float | None
    future_mdd: float | None


def compute_labels(
    closes: Sequence[float], t: int, horizon: int, *, cost_bps: float,
) -> LabelSet:
    """Compute all four target types at position ``t`` for horizon
    ``horizon`` bars.

    ``cost_bps`` is per-side transaction cost in basis points (round-trip
    accounted for below).
    """
    n = len(closes)
    if t < 0 or t + horizon >= n:
        return LabelSet(None, None, None, None)
    c0 = closes[t]
    c_h = closes[t + horizon]
    if c0 <= 0 or c_h <= 0:
        return LabelSet(None, None, None, None)
    fwd_ret = math.log(c_h / c0)

    # Direction with cost-adjusted neutral zone (spec §Target construction).
    round_trip = 2.0 * cost_bps / 10_000.0
    if fwd_ret > round_trip:
        direction = 1
    elif fwd_ret < -round_trip:
        direction = -1
    else:
        direction = 0

    # Realized vol along the path (log-return stdev)
    path = closes[t : t + horizon + 1]
    log_rets = []
    for i in range(1, len(path)):
        if path[i - 1] > 0 and path[i] > 0:
            log_rets.append(math.log(path[i] / path[i - 1]))
    if len(log_rets) >= 2:
        mean = sum(log_rets) / len(log_rets)
        var = sum((r - mean) ** 2 for r in log_rets) / (len(log_rets) - 1)
        future_vol = math.sqrt(var * 252)  # annualized
    else:
        future_vol = None

    # Max adverse move: min close on the path relative to entry
    if len(path) >= 2:
        low_along_path = min(path[1:])
        mdd = (low_along_path - c0) / c0
    else:
        mdd = None

    return LabelSet(
        direction=direction,
        future_return=fwd_ret,
        future_vol=future_vol,
        future_mdd=mdd,
    )
