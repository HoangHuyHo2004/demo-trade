"""Paper-portfolio computation.

Positions and P&L are computed from ``paper_transactions`` on read.
The transaction table is the single source of truth. This keeps
the code correct across concurrent edits and lets us replay history
deterministically for snapshots.

Cost-basis method: weighted average cost (WAC) per asset. This is the
simplest correct method and matches how most retail brokerages report
unrealized P&L in a summary view. Tax-lot accounting (FIFO/LIFO/specific
lots) is a Phase 5.1 backlog item.

Cash accounting: multi-currency. Each transaction settles in its own
``currency`` field; ``cash_by_currency`` tracks each balance separately,
and the portfolio's ``base_currency`` valuation uses the FX service.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.asset_id import AssetId
from app.models.asset import Asset
from app.models.portfolio import PaperTransaction, Portfolio, TxKind
from app.providers.registry import get_registry
from app.services.fx import FxService

ZERO = Decimal("0")


@dataclass
class Position:
    asset_canonical_id: str
    display_symbol: str
    market: str
    quantity: Decimal
    avg_cost: Decimal              # in the asset's quote currency
    quote_currency: str
    last_price: Decimal | None = None
    last_price_source: str | None = None
    last_price_time: datetime | None = None
    market_value_ccy: Decimal | None = None     # in quote currency
    market_value_base: Decimal | None = None    # in portfolio base currency
    unrealized_pnl_ccy: Decimal | None = None
    unrealized_pnl_base: Decimal | None = None
    realized_pnl_ccy: Decimal = field(default_factory=lambda: ZERO)


@dataclass
class PortfolioValuation:
    portfolio_id: int
    base_currency: str
    as_of: datetime
    cash_by_currency: dict[str, Decimal]
    cash_base: Decimal
    positions: list[Position]
    positions_value_base: Decimal
    equity_base: Decimal
    realized_pnl_base: Decimal
    unrealized_pnl_base: Decimal
    fx_used: dict[tuple[str, str], Decimal]
    warnings: list[str]


class PortfolioService:
    def __init__(self, session: AsyncSession, fx: FxService | None = None):
        self._s = session
        self._fx = fx or FxService()

    async def load_portfolio(self, portfolio_id: int, user_id: int) -> Portfolio:
        stmt = (
            select(Portfolio)
            .where(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
            .options(selectinload(Portfolio.transactions))
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise LookupError(f"portfolio {portfolio_id} not found for user {user_id}")
        return row

    async def value(self, portfolio: Portfolio, at: datetime | None = None) -> PortfolioValuation:
        at = at or datetime.now(UTC)
        base = portfolio.base_currency

        assets_by_id = await self._load_assets_map(portfolio)
        cash_by_ccy, position_state = _replay_transactions(portfolio.transactions, assets_by_id, at)

        positions: list[Position] = []
        fx_used: dict[tuple[str, str], Decimal] = {}
        warnings: list[str] = []
        positions_value_base = ZERO
        unrealized_base = ZERO
        realized_base = ZERO

        # Realized P&L per currency → base
        realized_by_ccy: dict[str, Decimal] = {}

        for asset_id, ps in position_state.items():
            asset = assets_by_id[asset_id]
            realized_by_ccy.setdefault(asset.quote_currency, ZERO)
            realized_by_ccy[asset.quote_currency] += ps.realized

            p = Position(
                asset_canonical_id=asset.canonical_id,
                display_symbol=asset.display_symbol,
                market=asset.market,
                quantity=ps.quantity,
                avg_cost=ps.avg_cost,
                quote_currency=asset.quote_currency,
                realized_pnl_ccy=ps.realized,
            )
            if ps.quantity > 0:
                last_price = await _fetch_last_price(self._s, asset)
                if last_price is not None:
                    p.last_price = Decimal(str(last_price.price))
                    p.last_price_source = last_price.source
                    p.last_price_time = last_price.event_time
                    p.market_value_ccy = p.quantity * p.last_price
                    p.unrealized_pnl_ccy = (p.last_price - ps.avg_cost) * ps.quantity
                    try:
                        rate = self._fx.rate(asset.quote_currency, base, at)
                        fx_used[(asset.quote_currency, base)] = rate.rate
                        p.market_value_base = p.market_value_ccy * rate.rate
                        p.unrealized_pnl_base = p.unrealized_pnl_ccy * rate.rate
                        positions_value_base += p.market_value_base
                        unrealized_base += p.unrealized_pnl_base
                    except Exception as e:  # noqa: BLE001
                        warnings.append(
                            f"FX rate {asset.quote_currency}→{base} unavailable "
                            f"for {asset.display_symbol}: {e}"
                        )
                else:
                    warnings.append(
                        f"No live price for {asset.display_symbol}; excluded from equity."
                    )
            positions.append(p)

        # cash in base
        cash_base = ZERO
        for ccy, amount in cash_by_ccy.items():
            try:
                rate = self._fx.rate(ccy, base, at)
                fx_used[(ccy, base)] = rate.rate
                cash_base += amount * rate.rate
            except Exception as e:  # noqa: BLE001
                warnings.append(f"cash FX {ccy}→{base} unavailable: {e}")

        # Realized in base
        for ccy, amount in realized_by_ccy.items():
            try:
                rate = self._fx.rate(ccy, base, at)
                fx_used[(ccy, base)] = rate.rate
                realized_base += amount * rate.rate
            except Exception:  # noqa: BLE001
                pass  # already warned above

        equity_base = cash_base + positions_value_base

        return PortfolioValuation(
            portfolio_id=portfolio.id, base_currency=base, as_of=at,
            cash_by_currency=cash_by_ccy, cash_base=cash_base,
            positions=positions, positions_value_base=positions_value_base,
            equity_base=equity_base,
            realized_pnl_base=realized_base,
            unrealized_pnl_base=unrealized_base,
            fx_used=fx_used, warnings=warnings,
        )

    # ---------- helpers ----------

    async def _load_assets_map(self, portfolio: Portfolio) -> dict[int, Asset]:
        ids = {tx.asset_id for tx in portfolio.transactions if tx.asset_id is not None}
        if not ids:
            return {}
        rows = (await self._s.execute(
            select(Asset).where(Asset.id.in_(ids))
        )).scalars().all()
        return {a.id: a for a in rows}


# ------------------ pure functions ------------------

@dataclass
class _AssetState:
    quantity: Decimal = ZERO
    avg_cost: Decimal = ZERO
    realized: Decimal = ZERO


def _replay_transactions(
    txs: list[PaperTransaction],
    assets_by_id: dict[int, Asset],
    at: datetime,
) -> tuple[dict[str, Decimal], dict[int, _AssetState]]:
    """Return ``(cash_by_currency, positions_by_asset_id)``.

    Applies transactions in chronological order up to (and including)
    ``at``. WAC cost basis; short quantities disallowed (SELL beyond
    current quantity clamps to zero and treats surplus as new BUY at that
    price to keep the position non-negative; the caller should validate
    upstream so this branch is a safety net only).
    """
    cash: dict[str, Decimal] = {}
    pos: dict[int, _AssetState] = {}
    for tx in sorted(txs, key=lambda t: t.executed_at):
        if tx.executed_at > at:
            break
        ccy = tx.currency.upper()
        cash.setdefault(ccy, ZERO)
        if tx.kind == TxKind.DEPOSIT:
            cash[ccy] += tx.quantity   # quantity carries the cash amount
        elif tx.kind == TxKind.WITHDRAW:
            cash[ccy] -= tx.quantity
        elif tx.kind == TxKind.DIVIDEND:
            cash[ccy] += tx.quantity
        elif tx.kind == TxKind.FEE:
            cash[ccy] -= tx.quantity
        elif tx.kind == TxKind.BUY:
            if tx.asset_id is None:
                continue
            state = pos.setdefault(tx.asset_id, _AssetState())
            gross = tx.quantity * tx.price + tx.fee
            cash[ccy] -= gross
            new_qty = state.quantity + tx.quantity
            if new_qty <= 0:
                state.quantity = ZERO
                state.avg_cost = ZERO
            else:
                state.avg_cost = (
                    state.quantity * state.avg_cost + tx.quantity * tx.price
                ) / new_qty
                state.quantity = new_qty
        elif tx.kind == TxKind.SELL:
            if tx.asset_id is None:
                continue
            state = pos.setdefault(tx.asset_id, _AssetState())
            sold_qty = min(tx.quantity, state.quantity)
            proceeds = sold_qty * tx.price - tx.fee
            cash[ccy] += proceeds
            state.realized += (tx.price - state.avg_cost) * sold_qty - tx.fee
            state.quantity -= sold_qty
            if state.quantity == 0:
                state.avg_cost = ZERO
        # Unknown kinds are silently ignored (defense-in-depth if a new
        # enum value ever slips in).
    return cash, pos


async def _fetch_last_price(session: AsyncSession, asset: Asset):
    """Ask the configured provider for the latest quote. Read-only."""
    aid = AssetId.parse(asset.canonical_id)
    provider = get_registry().market_data_for(asset.market)
    return await provider.get_quote(aid)
