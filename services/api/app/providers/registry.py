"""Provider registry — selects concrete adapters based on config + credentials.

Selection rules per market (Phase 2):
  * COINBASE → CoinbaseProvider (public, no key). Always active unless
    ``DEMO_MODE`` and ``FORCE_MOCK`` explicitly set.
  * US       → AlpacaProvider if ``ALPACA_API_KEY``+SECRET present, else mock.
  * VN       → SSIFastConnectProvider if ``SSI_FC_CONSUMER_ID``+SECRET
               present, else mock.

Every configured provider gets an entry in the status list so operators
can see at a glance what is active vs missing credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.alpaca import AlpacaProvider
from app.providers.base import MarketDataProvider
from app.providers.coinbase import CoinbaseProvider
from app.providers.mock import MockMarketDataProvider
from app.providers.ssi import SSIFastConnectProvider

log = get_logger(__name__)


@dataclass(frozen=True)
class ProviderInfo:
    slug: str
    kind: str  # market_data, fundamentals, ...
    status: str  # ok, degraded, down, unknown, missing_credentials
    message: str
    markets: tuple[str, ...]
    is_selected_for: tuple[str, ...]  # markets currently routed to this provider


class ProviderRegistry:
    def __init__(
        self,
        *,
        market_data_by_market: dict[str, MarketDataProvider],
        all_market_data: list[tuple[MarketDataProvider, str]],  # (provider, status)
    ):
        self._by_market = market_data_by_market
        # tuples so we can report status for providers that exist but
        # are not selected (missing_credentials, forced-mock).
        self._all = all_market_data

    def market_data_for(self, market: str) -> MarketDataProvider:
        if market in self._by_market:
            return self._by_market[market]
        # Ultimate fallback — the mock is always registered.
        for p, _ in self._all:
            if p.slug == "mock":
                return p
        raise RuntimeError("no market-data provider available")

    def list_status(self) -> list[ProviderInfo]:
        out: list[ProviderInfo] = []
        for p, status in self._all:
            selected = tuple(
                m for m, chosen in self._by_market.items() if chosen is p
            )
            out.append(ProviderInfo(
                slug=p.slug,
                kind="market_data",
                status=status,
                message=_message_for(p, status),
                markets=p.supports_markets,
                is_selected_for=selected,
            ))
        return out


def _message_for(p: MarketDataProvider, status: str) -> str:
    if status == "missing_credentials":
        return f"{p.slug}: credentials not configured; falling back to mock"
    if status == "ok":
        return f"{p.slug}: active (supports={','.join(p.supports_markets)})"
    return f"{p.slug}: {status}"


@lru_cache
def get_registry() -> ProviderRegistry:
    settings = get_settings()

    mock = MockMarketDataProvider()
    all_providers: list[tuple[MarketDataProvider, str]] = [(mock, "ok")]
    by_market: dict[str, MarketDataProvider] = {
        "US": mock, "VN": mock, "COINBASE": mock,
        "KRAKEN": mock, "BINANCE": mock,
    }

    # Coinbase is public — always selected (even in demo mode) unless
    # explicitly disabled, since it exercises the real-provider path
    # end-to-end at zero cost.
    cb = CoinbaseProvider()
    by_market["COINBASE"] = cb
    all_providers.append((cb, "ok"))

    # Alpaca (US) — auto-select if credentials present.
    if settings.alpaca_api_key and settings.alpaca_api_secret:
        alp = AlpacaProvider()
        by_market["US"] = alp
        all_providers.append((alp, "ok"))
    else:
        all_providers.append((AlpacaProvider(), "missing_credentials"))

    # SSI FastConnect (VN) — auto-select if credentials present.
    if settings.ssi_fc_consumer_id and settings.ssi_fc_consumer_secret:
        ssi = SSIFastConnectProvider()
        by_market["VN"] = ssi
        all_providers.append((ssi, "ok"))
    else:
        all_providers.append((SSIFastConnectProvider(), "missing_credentials"))

    log.info(
        "provider_registry_ready",
        selected={m: p.slug for m, p in by_market.items()},
        demo_mode=settings.demo_mode,
    )
    return ProviderRegistry(
        market_data_by_market=by_market,
        all_market_data=all_providers,
    )
