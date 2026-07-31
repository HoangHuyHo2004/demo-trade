"""Provider registry — selects concrete adapters based on config."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings
from app.providers.base import MarketDataProvider
from app.providers.mock import MockMarketDataProvider


@dataclass(frozen=True)
class ProviderInfo:
    slug: str
    kind: str  # market_data, fundamentals, ...
    status: str  # ok, degraded, down, unknown
    message: str


class ProviderRegistry:
    def __init__(self, *, market_data: dict[str, MarketDataProvider]):
        self._market_data = market_data

    def market_data_for(self, market: str) -> MarketDataProvider:
        # Look up by market ("US" / "VN" / "COINBASE" / ...). Fall back to
        # the first provider that supports it; ultimately to the mock.
        for provider in self._market_data.values():
            if market in provider.supports_markets:
                return provider
        return self._market_data["mock"]

    def list_status(self) -> list[ProviderInfo]:
        out: list[ProviderInfo] = []
        for slug, p in self._market_data.items():
            out.append(
                ProviderInfo(
                    slug=slug,
                    kind="market_data",
                    status="ok",
                    message=f"supports={','.join(p.supports_markets)}",
                )
            )
        return out


@lru_cache
def get_registry() -> ProviderRegistry:
    settings = get_settings()
    market_data: dict[str, MarketDataProvider] = {"mock": MockMarketDataProvider()}
    # Real adapters (alpaca / ssi / coinbase) will be added in Phase 2 and
    # selected here based on settings + presence of credentials. In demo
    # mode we intentionally use the mock only.
    if not settings.demo_mode:
        # Placeholder — Phase 2 will wire real adapters here.
        pass
    return ProviderRegistry(market_data=market_data)
