"""Portfolio math: cash flows, WAC cost basis, realized/unrealized P&L."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.asset import Asset
from app.models.portfolio import PaperTransaction, Portfolio, TxKind
from app.models.user import User
from app.services.portfolio import PortfolioService, _replay_transactions


async def _seed(session) -> tuple[User, Asset, Asset]:
    u = User(email="user@x", display_name="U")
    session.add(u)
    a = Asset(
        canonical_id="EQUITY:US:NASDAQ:AAPL",
        asset_type="EQUITY", market="US", exchange_code="NASDAQ",
        symbol="AAPL", display_symbol="AAPL", name="Apple",
        quote_currency="USD", market_timezone="America/New_York",
        calendar="XNYS",
    )
    v = Asset(
        canonical_id="EQUITY:VN:HOSE:VNM",
        asset_type="EQUITY", market="VN", exchange_code="HOSE",
        symbol="VNM", display_symbol="VNM", name="Vinamilk",
        quote_currency="VND", market_timezone="Asia/Ho_Chi_Minh",
        calendar="XHOS",
    )
    session.add(a); session.add(v)
    await session.commit()
    await session.refresh(u); await session.refresh(a); await session.refresh(v)
    return u, a, v


def _tx(pid, kind, asset_id=None, qty="0", price="0", ccy="USD", fee="0", when=None):
    return PaperTransaction(
        portfolio_id=pid, asset_id=asset_id, kind=kind,
        quantity=Decimal(qty), price=Decimal(price), currency=ccy,
        fee=Decimal(fee),
        executed_at=(when or datetime.now(UTC)),
        created_at=datetime.now(UTC),
    )


def test_replay_deposit_then_buy_then_sell_wac():
    now = datetime(2024, 1, 1, tzinfo=UTC)
    txs = [
        _tx(1, TxKind.DEPOSIT, qty="10000", ccy="USD", when=now),
        _tx(1, TxKind.BUY, asset_id=1, qty="10", price="100", ccy="USD",
            when=now + timedelta(days=1)),
        _tx(1, TxKind.BUY, asset_id=1, qty="10", price="120", ccy="USD",
            when=now + timedelta(days=2)),
        _tx(1, TxKind.SELL, asset_id=1, qty="5", price="150", ccy="USD",
            when=now + timedelta(days=3)),
    ]
    cash, pos = _replay_transactions(
        txs, assets_by_id={1: object()}, at=now + timedelta(days=30),
    )
    # cash: 10000 - 10*100 - 10*120 + 5*150 = 10000 - 1000 - 1200 + 750 = 8550
    assert cash["USD"] == Decimal("8550")
    # WAC after buys: (10*100 + 10*120) / 20 = 110
    # After selling 5, quantity=15, avg_cost stays 110
    p = pos[1]
    assert p.quantity == Decimal("15")
    assert p.avg_cost == Decimal("110")
    # realized: (150 - 110) * 5 = 200
    assert p.realized == Decimal("200")


def test_replay_stops_at_time_boundary():
    now = datetime(2024, 1, 1, tzinfo=UTC)
    txs = [
        _tx(1, TxKind.DEPOSIT, qty="100", ccy="USD", when=now),
        _tx(1, TxKind.DEPOSIT, qty="50", ccy="USD", when=now + timedelta(days=10)),
    ]
    cash, _ = _replay_transactions(txs, assets_by_id={}, at=now + timedelta(days=5))
    assert cash["USD"] == Decimal("100")


def test_sell_beyond_holding_clamps_to_zero_and_realizes_available():
    now = datetime(2024, 1, 1, tzinfo=UTC)
    txs = [
        _tx(1, TxKind.BUY, asset_id=1, qty="5", price="10", ccy="USD", when=now),
        _tx(1, TxKind.SELL, asset_id=1, qty="10", price="20", ccy="USD",
            when=now + timedelta(days=1)),
    ]
    cash, pos = _replay_transactions(
        txs, assets_by_id={1: object()}, at=now + timedelta(days=30),
    )
    assert pos[1].quantity == Decimal("0")
    # realized = (20 - 10) * 5 sold = 50
    assert pos[1].realized == Decimal("50")
    # cash: -5*10 + 5*20 = 50
    assert cash["USD"] == Decimal("50")


def test_dividend_and_fee_are_pure_cash():
    now = datetime(2024, 1, 1, tzinfo=UTC)
    txs = [
        _tx(1, TxKind.DIVIDEND, asset_id=1, qty="12.34", ccy="USD", when=now),
        _tx(1, TxKind.FEE, qty="1", ccy="USD", when=now + timedelta(days=1)),
    ]
    cash, pos = _replay_transactions(
        txs, assets_by_id={1: object()}, at=now + timedelta(days=30),
    )
    assert cash["USD"] == Decimal("11.34")
    assert pos == {} or (pos and pos[1].quantity == 0)


@pytest.mark.asyncio
async def test_valuation_end_to_end(session):
    u, aapl, vnm = await _seed(session)
    p = Portfolio(user_id=u.id, name="Main", base_currency="USD")
    session.add(p); await session.commit(); await session.refresh(p)

    now = datetime(2024, 6, 1, tzinfo=UTC)
    txs = [
        _tx(p.id, TxKind.DEPOSIT, qty="10000", ccy="USD",
            when=now - timedelta(days=30)),
        _tx(p.id, TxKind.BUY, asset_id=aapl.id, qty="5", price="150",
            ccy="USD", when=now - timedelta(days=20)),
        # VN buy — will trigger USD→VND FX
        _tx(p.id, TxKind.DEPOSIT, qty="25000000", ccy="VND",
            when=now - timedelta(days=15)),
        _tx(p.id, TxKind.BUY, asset_id=vnm.id, qty="100", price="70000",
            ccy="VND", when=now - timedelta(days=10)),
    ]
    for t in txs:
        session.add(t)
    await session.commit()

    svc = PortfolioService(session)
    portfolio = await svc.load_portfolio(p.id, u.id)
    val = await svc.value(portfolio, at=now)
    assert val.base_currency == "USD"
    # Two positions expected
    assert len(val.positions) == 2
    aapl_pos = next(x for x in val.positions if x.display_symbol == "AAPL")
    assert aapl_pos.quantity == Decimal("5")
    assert aapl_pos.avg_cost == Decimal("150")
    # Live price is served by the mock provider; equity should be > cash alone.
    assert val.equity_base > 0
    # No FX warnings for a properly-priced portfolio
    assert not any("unavailable" in w for w in val.warnings), val.warnings
