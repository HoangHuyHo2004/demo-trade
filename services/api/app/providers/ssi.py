"""SSI FastConnect Data (Vietnam) market-data adapter — Phase 2 skeleton.

SSI FastConnect is a paid, contract-required service. This adapter is a
credential-gated skeleton: without ``SSI_FC_CONSUMER_ID`` and
``SSI_FC_CONSUMER_SECRET`` set, the registry will select the mock
provider for VN markets instead.

The methods below intentionally raise ``NotImplementedError`` when
called without an OAuth token bootstrap — the full flow (token refresh,
history endpoint pagination, calendar reconciliation) lands in a
dedicated ticket during Phase 2 hardening. Adding it requires a signed
SSI contract; see ``docs/data-licensing-checklist.md``.
"""
from __future__ import annotations

from datetime import datetime

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.asset_id import AssetId, Market
from app.providers.base import BarDTO, MarketDataProvider, QuoteDTO

log = get_logger(__name__)


class SSIFastConnectProvider(MarketDataProvider):
    slug = "ssi-fc"
    supports_markets = ("VN",)

    def __init__(self) -> None:
        s = get_settings()
        self.consumer_id = s.ssi_fc_consumer_id
        self.consumer_secret = s.ssi_fc_consumer_secret
        self.base_url = s.ssi_fc_api_url
        if not self.consumer_id or not self.consumer_secret:
            log.info("ssi_fc_skipped_missing_creds")

    async def _ensure_creds(self) -> None:
        if not self.consumer_id or not self.consumer_secret:
            raise RuntimeError(
                "SSI FastConnect credentials missing; registry should have "
                "selected the mock provider instead"
            )

    @staticmethod
    def _validate(asset: AssetId) -> None:
        if asset.market is not Market.VN:
            raise ValueError(f"SSIFastConnectProvider only supports VN assets, got {asset}")

    async def get_quote(self, asset: AssetId) -> QuoteDTO:
        self._validate(asset)
        await self._ensure_creds()
        raise NotImplementedError(
            "SSI FastConnect real-quote fetch requires a signed contract; "
            "see docs/data-licensing-checklist.md"
        )

    async def get_bars(
        self, asset: AssetId, *, interval: str, start: datetime, end: datetime
    ) -> list[BarDTO]:
        self._validate(asset)
        await self._ensure_creds()
        raise NotImplementedError(
            "SSI FastConnect historical bars requires a signed contract; "
            "see docs/data-licensing-checklist.md"
        )
