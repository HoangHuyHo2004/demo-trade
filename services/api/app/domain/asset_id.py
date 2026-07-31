"""Canonical asset identity.

Format:
  * Equities / ETFs / indices: ``{TYPE}:{MARKET}:{EXCHANGE}:{SYMBOL}``
    e.g. ``EQUITY:US:NASDAQ:AAPL``, ``EQUITY:VN:HOSE:VNM``,
    ``INDEX:VN:HOSE:VNINDEX``.
  * Crypto: ``CRYPTO:{EXCHANGE}:{SYMBOL}`` (3-part; market==exchange).
    e.g. ``CRYPTO:COINBASE:BTC-USD``.

A ticker on its own is never a primary identifier because tickers collide
across markets (e.g. VN ``ACB`` vs a US-listed ETF ticker). Callers must
resolve ambiguous inputs through :mod:`app.services.symbol_resolver`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class AssetType(StrEnum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    CRYPTO = "CRYPTO"
    INDEX = "INDEX"


class Market(StrEnum):
    US = "US"
    VN = "VN"
    COINBASE = "COINBASE"
    KRAKEN = "KRAKEN"
    BINANCE = "BINANCE"


US_EXCHANGES = {"NASDAQ", "NYSE", "AMEX", "ARCA", "BATS"}
VN_EXCHANGES = {"HOSE", "HNX", "UPCOM"}
CRYPTO_EXCHANGES = {"COINBASE", "KRAKEN", "BINANCE"}

_SYMBOL_RE = re.compile(r"^[A-Z0-9._-]{1,32}$")


@dataclass(frozen=True, slots=True)
class AssetId:
    asset_type: AssetType
    market: Market
    exchange: str
    symbol: str

    def __str__(self) -> str:
        if self.asset_type is AssetType.CRYPTO:
            return f"{self.asset_type}:{self.exchange}:{self.symbol}"
        return f"{self.asset_type}:{self.market}:{self.exchange}:{self.symbol}"

    @property
    def canonical(self) -> str:
        return str(self)

    @classmethod
    def parse(cls, raw: str) -> AssetId:
        if not raw or not isinstance(raw, str):
            raise ValueError("asset id must be a non-empty string")
        parts = raw.strip().split(":")
        if len(parts) == 3 and parts[0] == AssetType.CRYPTO.value:
            atype_s, exchange, symbol = parts
            market_s = exchange  # for crypto, market == exchange
        elif len(parts) == 4:
            atype_s, market_s, exchange, symbol = parts
        else:
            raise ValueError(
                f"asset id must be TYPE:MARKET:EXCHANGE:SYMBOL "
                f"(or CRYPTO:EXCHANGE:SYMBOL); got {raw!r}"
            )

        try:
            atype = AssetType(atype_s)
        except ValueError as e:
            raise ValueError(f"invalid asset type: {atype_s!r}") from e
        try:
            market = Market(market_s)
        except ValueError as e:
            raise ValueError(f"invalid market: {market_s!r}") from e

        exchange = exchange.upper()
        symbol = symbol.upper()
        if not _SYMBOL_RE.match(symbol):
            raise ValueError(f"invalid symbol: {symbol!r}")
        _validate_combination(atype, market, exchange)
        return cls(atype, market, exchange, symbol)


def _validate_combination(atype: AssetType, market: Market, exchange: str) -> None:
    if atype in (AssetType.EQUITY, AssetType.ETF, AssetType.INDEX):
        if market is Market.US and exchange not in US_EXCHANGES:
            raise ValueError(f"unknown US exchange: {exchange!r}")
        if market is Market.VN and exchange not in VN_EXCHANGES:
            raise ValueError(f"unknown VN exchange: {exchange!r}")
        if market not in (Market.US, Market.VN):
            raise ValueError(f"equity/etf/index requires US or VN market, got {market}")
    elif atype is AssetType.CRYPTO:
        if market.value not in CRYPTO_EXCHANGES:
            raise ValueError(f"crypto requires an exchange market, got {market}")
        if exchange != market.value:
            raise ValueError(
                f"crypto market and exchange must match ({market} vs {exchange})"
            )
