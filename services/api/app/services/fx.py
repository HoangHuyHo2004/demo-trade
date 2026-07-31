"""FX conversion (demo-mode dated fixed-rate table).

Production must replace ``DEMO_RATES`` with a live FX provider adapter
using the same shape. Keeping the interface stable so business code
doesn't move when that swap happens.

Rules:
  * Same currency: no-op (rate = 1).
  * Missing pair: raise ``FxRateMissing`` — never silently return 1.
  * Rates are direct: ``rate(USD, VND) = 25_000`` means 1 USD = 25 000 VND.
  * If the rate is only known one direction, ``rate(b, a) = 1 / rate(a, b)``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

# Direct rates, base → quote. Kept minimal.
DEMO_RATES: dict[tuple[str, str], Decimal] = {
    ("USD", "VND"): Decimal("25000"),
    ("USD", "EUR"): Decimal("0.93"),
}


class FxRateMissing(Exception):
    pass


@dataclass(frozen=True)
class FxRate:
    base: str
    quote: str
    rate: Decimal
    as_of: datetime
    source: str


class FxService:
    """Deterministic FX. In Phase 5 the rates are static — the ``as_of``
    is stamped so calling code and audits can always tell what rate was
    applied.
    """

    def __init__(self, rates: dict[tuple[str, str], Decimal] | None = None,
                 source: str = "demo-fixed"):
        self._rates = rates if rates is not None else DEMO_RATES
        self._source = source

    def rate(self, base: str, quote: str, at: datetime | None = None) -> FxRate:
        base = base.upper()
        quote = quote.upper()
        at = at or datetime.now(UTC)
        if base == quote:
            return FxRate(base, quote, Decimal("1"), at, self._source)
        r = self._rates.get((base, quote))
        if r is not None:
            return FxRate(base, quote, r, at, self._source)
        inv = self._rates.get((quote, base))
        if inv is not None and inv != 0:
            return FxRate(base, quote, Decimal("1") / inv, at, self._source)
        raise FxRateMissing(f"no FX rate available: {base} → {quote}")

    def convert(self, amount: Decimal, base: str, quote: str,
                at: datetime | None = None) -> Decimal:
        return amount * self.rate(base, quote, at).rate

    def known_pairs(self) -> list[tuple[str, str]]:
        return sorted(self._rates.keys())


# Silence unused-import lints when only the class is referenced.
_ = date
