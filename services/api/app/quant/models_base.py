"""Pluggable signal-model interface.

The engine imports concrete models from this package and dispatches to
them by ``code``. The rule-based ensemble ships in Phase 3; ML models
can be added later without any change to the API contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SignalInput:
    """Everything the model can see at ``as_of``.

    All sequences are aligned, oldest → newest. The caller MUST have
    filtered every value's ``available_at <= as_of`` before building this
    object — the model never touches raw timestamps or provider data.
    """
    asset_canonical_id: str
    market: str
    quote_currency: str
    calendar: str
    is_benchmark: bool

    interval: str
    as_of: datetime
    times: list[datetime]      # bar timestamps aligned to closes
    open_: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]

    # Aligned benchmark closes (same times). Optional; None when we don't
    # have a benchmark for this asset's market.
    benchmark_close: list[float] | None
    benchmark_symbol: str | None


@dataclass(frozen=True, slots=True)
class ModelOutput:
    """What a model returns to the engine.

    The engine wraps this in the API-facing envelope (classification
    thresholds, disclaimers, versions).
    """
    score: float                # -100..100 raw score
    factors: list[FactorContribution]
    regime: str                 # BULL/BEAR/NEUTRAL, computed by the model
    data_quality: float         # 0..1
    liquidity_warnings: list[str]
    contradictions: list[str]
    positive_factors: list[FactorContribution]
    negative_factors: list[FactorContribution]
    # Optional reference levels — only set when statistically defensible.
    entry_zone: tuple[float, float] | None
    invalidation: float | None
    take_profit: list[float]


@dataclass(frozen=True, slots=True)
class FactorContribution:
    code: str
    label: str
    category: str          # trend, momentum, volatility, volume, breadth, benchmark
    contribution: float    # -1..1
    detail: str = ""


class SignalModel(ABC):
    code: str          # unique version id, e.g. "ensemble-v1"
    family: str        # ensemble | ml
    description: str = ""

    @abstractmethod
    def compute(self, si: SignalInput, *, horizon: str) -> ModelOutput:  # pragma: no cover
        ...
