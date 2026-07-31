"""Typed tool schemas + shared research-response envelope.

Everything the agent can send or receive is Pydantic-validated. Unknown
fields are rejected server-side so a compromised or hallucinated tool
call cannot smuggle extra parameters through.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Horizon = Literal["1D", "5D", "20D"]
Interval = Literal["1m", "15m", "1h", "1d", "1w", "1mo"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- tool argument schemas ----------

class ResolveAssetArgs(_Strict):
    query: str = Field(..., min_length=1, max_length=64)
    market: Literal["US", "VN", "COINBASE", "KRAKEN", "BINANCE"] | None = None
    asset_type: Literal["EQUITY", "ETF", "CRYPTO", "INDEX"] | None = None


class GetMarketStatusArgs(_Strict):
    market: Literal["US", "VN", "CRYPTO"] | None = None


class GetQuoteArgs(_Strict):
    asset_canonical_id: str = Field(..., min_length=3, max_length=96)


class GetHistoricalBarsArgs(_Strict):
    asset_canonical_id: str = Field(..., min_length=3, max_length=96)
    interval: Interval = "1d"
    lookback_days: int = Field(90, ge=1, le=3650)


class GetCalculatedIndicatorsArgs(_Strict):
    asset_canonical_id: str = Field(..., min_length=3, max_length=96)
    interval: Interval = "1d"
    lookback_days: int = Field(180, ge=30, le=3650)
    indicators: list[Literal["sma20", "sma50", "sma200", "ema20", "ema60",
                              "rsi14", "macd", "atr14", "realized_vol20",
                              "momentum_20", "momentum_60"]] = Field(default_factory=list)


class CalculateSignalArgs(_Strict):
    asset_canonical_id: str = Field(..., min_length=3, max_length=96)
    horizon: Horizon = "5D"
    model: str = Field("ensemble-v1", max_length=64)


class RunBacktestArgs(_Strict):
    asset_canonical_id: str = Field(..., min_length=3, max_length=96)
    interval: Interval = "1d"
    horizon: Horizon = "5D"
    entry_threshold: float = Field(20.0, ge=-100.0, le=100.0)
    exit_threshold: float = Field(-5.0, ge=-100.0, le=100.0)
    lookback_days: int = Field(365, ge=60, le=3650)


class CompareAssetsArgs(_Strict):
    asset_canonical_ids: list[str] = Field(..., min_length=2, max_length=5)
    interval: Interval = "1d"
    lookback_days: int = Field(180, ge=1, le=3650)


class SearchStubArgs(_Strict):
    """Shared shape for the deferred search tools.

    These tools are advertised so the model knows they exist, but they
    always return ``status="not_available"`` so the agent must abstain
    when asked to cite filings/news/disclosures.
    """
    asset_canonical_id: str | None = Field(None, min_length=3, max_length=96)
    query: str = Field(..., min_length=1, max_length=200)
    limit: int = Field(5, ge=1, le=20)


# ---------- shared response envelope (research chat) ----------

class SourceCitation(BaseModel):
    title: str
    publisher: str
    url: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    kind: str = "system"  # system | filing | disclosure | news | project | quantitative
    asset_canonical_id: str | None = None


class ResearchResponse(BaseModel):
    """Structured output the agent MUST return to the user.

    The engine constructs this from the model's final message so the UI
    can render facts vs interpretation with visible separation.
    """
    asset_canonical_id: str | None = None
    executive_summary: str
    current_trend: str = ""
    signal_summary: str = ""
    bull_case: list[str] = Field(default_factory=list)
    bear_case: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    upcoming_catalysts: list[str] = Field(default_factory=list)
    data_quality_warnings: list[str] = Field(default_factory=list)
    verified_facts: list[str] = Field(default_factory=list)
    interpretation: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    citations: list[SourceCitation] = Field(default_factory=list)
    abstained: bool = False
    abstention_reason: str = ""
