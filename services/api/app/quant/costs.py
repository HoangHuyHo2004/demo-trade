"""Dated cost profiles per market.

Kept out of code paths so operators can dial these without touching
strategy logic. Real production profiles should be persisted in the DB
with effective-dated rows; the constants here are engineering defaults
for the MVP.

Costs are per side (entry OR exit), in basis points of notional.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostProfile:
    market: str
    fee_bps: float          # commission / exchange fee
    slippage_bps: float     # execution slippage assumption
    tax_bps: float = 0.0    # transfer/turnover tax if any

    @property
    def total_bps(self) -> float:
        return self.fee_bps + self.slippage_bps + self.tax_bps


DEFAULT_PROFILES: dict[str, CostProfile] = {
    "US": CostProfile("US", fee_bps=0.0, slippage_bps=3.0),
    # VN retail: HOSE commission ≈ 15bps typical + 10bps transfer tax on sells
    # (we apply symmetrically per side for a conservative pass; docs note this).
    "VN": CostProfile("VN", fee_bps=15.0, slippage_bps=10.0, tax_bps=5.0),
    "COINBASE": CostProfile("COINBASE", fee_bps=40.0, slippage_bps=5.0),
    "KRAKEN": CostProfile("KRAKEN", fee_bps=25.0, slippage_bps=5.0),
    "BINANCE": CostProfile("BINANCE", fee_bps=10.0, slippage_bps=5.0),
}


def profile_for(market: str) -> CostProfile:
    return DEFAULT_PROFILES.get(market, CostProfile(market, fee_bps=5.0, slippage_bps=5.0))
