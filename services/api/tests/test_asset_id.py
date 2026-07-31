import pytest

from app.domain.asset_id import AssetId, AssetType, Market


def test_parse_us_equity():
    a = AssetId.parse("EQUITY:US:NASDAQ:AAPL")
    assert a.asset_type is AssetType.EQUITY
    assert a.market is Market.US
    assert a.exchange == "NASDAQ"
    assert a.symbol == "AAPL"
    assert str(a) == "EQUITY:US:NASDAQ:AAPL"


def test_parse_vn_equity():
    a = AssetId.parse("EQUITY:VN:HOSE:VNM")
    assert a.market is Market.VN
    assert a.exchange == "HOSE"


def test_parse_crypto_three_part():
    a = AssetId.parse("CRYPTO:COINBASE:BTC-USD")
    assert a.asset_type is AssetType.CRYPTO
    assert a.market is Market.COINBASE
    assert a.exchange == "COINBASE"
    assert a.symbol == "BTC-USD"
    # canonical string is 3-part for crypto
    assert str(a) == "CRYPTO:COINBASE:BTC-USD"


def test_parse_crypto_four_part_also_allowed():
    a = AssetId.parse("CRYPTO:COINBASE:COINBASE:BTC-USD")
    assert str(a) == "CRYPTO:COINBASE:BTC-USD"  # normalized to 3-part on output


def test_bad_shape():
    with pytest.raises(ValueError):
        AssetId.parse("AAPL")


def test_bad_market_for_type():
    with pytest.raises(ValueError):
        AssetId.parse("EQUITY:COINBASE:NASDAQ:AAPL")


def test_bad_crypto_exchange_mismatch():
    with pytest.raises(ValueError):
        AssetId.parse("CRYPTO:COINBASE:KRAKEN:BTC-USD")


def test_bad_symbol_chars():
    with pytest.raises(ValueError):
        AssetId.parse("EQUITY:US:NASDAQ:aa pl")
