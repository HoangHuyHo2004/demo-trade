from decimal import Decimal

import pytest

from app.services.fx import FxRateMissing, FxService


def test_same_currency_is_one():
    fx = FxService()
    r = fx.rate("USD", "USD")
    assert r.rate == Decimal("1")


def test_known_pair_direct():
    fx = FxService()
    r = fx.rate("USD", "VND")
    assert r.rate == Decimal("25000")


def test_inverse_pair_computed():
    fx = FxService()
    r = fx.rate("VND", "USD")
    # 1/25000 = 0.00004
    assert r.rate == Decimal("1") / Decimal("25000")


def test_convert_amount():
    fx = FxService()
    got = fx.convert(Decimal("2"), "USD", "VND")
    assert got == Decimal("50000")


def test_missing_pair_raises():
    fx = FxService(rates={})
    with pytest.raises(FxRateMissing):
        fx.rate("USD", "JPY")
