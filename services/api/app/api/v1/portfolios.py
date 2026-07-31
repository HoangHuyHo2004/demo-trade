from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.logging import get_logger
from app.deps import CurrentUserDep, SessionDep
from app.models.agent import AuditLog
from app.models.asset import Asset
from app.models.portfolio import PaperTransaction, Portfolio, TxKind
from app.services.portfolio import PortfolioService
from app.services.risk import compute_risk

router = APIRouter()
log = get_logger(__name__)


# ---------- schemas ----------

class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    base_currency: str = Field("USD", pattern=r"^[A-Z]{3}$")


class TransactionCreate(BaseModel):
    kind: str = Field(..., pattern=r"^(BUY|SELL|DEPOSIT|WITHDRAW|DIVIDEND|FEE)$")
    asset_canonical_id: str | None = Field(None, min_length=3, max_length=96)
    quantity: Decimal = Field(..., ge=Decimal(0))
    price: Decimal = Field(Decimal(0), ge=Decimal(0))
    currency: str = Field(..., pattern=r"^[A-Z]{3}$")
    fee: Decimal = Field(Decimal(0), ge=Decimal(0))
    executed_at: datetime | None = None
    note: str = Field("", max_length=500)


class PortfolioSummaryOut(BaseModel):
    id: int
    name: str
    base_currency: str


# ---------- routes ----------

@router.get("", response_model=list[PortfolioSummaryOut])
async def list_portfolios(session: SessionDep, user: CurrentUserDep) -> list[Portfolio]:
    rows = (await session.execute(
        select(Portfolio).where(Portfolio.user_id == user.id).order_by(Portfolio.name)
    )).scalars().all()
    return list(rows)


@router.post("", response_model=PortfolioSummaryOut, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    body: PortfolioCreate, session: SessionDep, user: CurrentUserDep,
) -> Portfolio:
    p = Portfolio(user_id=user.id, name=body.name, base_currency=body.base_currency)
    session.add(p)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="portfolio name already exists",
        ) from e
    await session.refresh(p)
    session.add(AuditLog(
        actor=f"user:{user.id}", event="portfolio_created",
        subject_type="portfolio", subject_id=str(p.id),
        payload_json=json.dumps({"name": p.name, "base_currency": p.base_currency}),
        created_at=datetime.now(UTC),
    ))
    await session.commit()
    return p


@router.get("/{portfolio_id}")
async def get_portfolio(
    portfolio_id: int, session: SessionDep, user: CurrentUserDep,
) -> dict:
    svc = PortfolioService(session)
    try:
        portfolio = await svc.load_portfolio(portfolio_id, user.id)
    except LookupError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    val = await svc.value(portfolio)
    return _serialize_valuation(portfolio, val)


@router.post(
    "/{portfolio_id}/transactions",
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    portfolio_id: int, body: TransactionCreate,
    session: SessionDep, user: CurrentUserDep,
) -> dict:
    portfolio = (await session.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id, Portfolio.user_id == user.id,
        )
    )).scalar_one_or_none()
    if portfolio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="portfolio not found")

    asset_id: int | None = None
    if body.kind in {"BUY", "SELL", "DIVIDEND"} and body.asset_canonical_id:
        asset = (await session.execute(
            select(Asset).where(Asset.canonical_id == body.asset_canonical_id)
        )).scalar_one_or_none()
        if asset is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="asset not found")
        asset_id = asset.id
    elif body.kind in {"BUY", "SELL"} and body.asset_canonical_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="asset required for BUY/SELL")

    if body.kind == "BUY" and body.quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="BUY quantity must be > 0")
    if body.kind == "SELL" and body.quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="SELL quantity must be > 0")

    tx = PaperTransaction(
        portfolio_id=portfolio.id,
        asset_id=asset_id,
        kind=body.kind,
        quantity=body.quantity,
        price=body.price,
        currency=body.currency,
        fee=body.fee,
        executed_at=(body.executed_at or datetime.now(UTC)),
        note=body.note,
        created_at=datetime.now(UTC),
    )
    session.add(tx)
    session.add(AuditLog(
        actor=f"user:{user.id}", event="portfolio_transaction_added",
        subject_type="portfolio", subject_id=str(portfolio.id),
        payload_json=json.dumps({
            "kind": body.kind, "asset": body.asset_canonical_id,
            "qty": str(body.quantity), "price": str(body.price),
            "ccy": body.currency, "fee": str(body.fee),
        }),
        created_at=datetime.now(UTC),
    ))
    await session.commit()
    await session.refresh(tx)
    return {"id": tx.id, "kind": tx.kind, "executed_at": tx.executed_at.isoformat()}


@router.get("/{portfolio_id}/risk")
async def get_risk(
    portfolio_id: int, session: SessionDep, user: CurrentUserDep,
    lookback_days: int = 180,
) -> dict:
    if not (30 <= lookback_days <= 3650):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="lookback_days out of range")
    svc = PortfolioService(session)
    try:
        portfolio = await svc.load_portfolio(portfolio_id, user.id)
    except LookupError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    val = await svc.value(portfolio)
    report = await compute_risk(session, val, lookback_days=lookback_days)
    return {
        "portfolio_id": report.portfolio_id,
        "base_currency": report.base_currency,
        "as_of": report.as_of.isoformat(),
        "total_equity_base": report.total_equity_base,
        "allocation_by_asset": report.allocation_by_asset,
        "allocation_by_market": report.allocation_by_market,
        "cash_weight": report.cash_weight,
        "hhi_asset": report.hhi_asset,
        "top_holding_weight": report.top_holding_weight,
        "n_holdings": report.n_holdings,
        "lookback_days": report.lookback_days,
        "volatility_annualized": report.volatility_annualized,
        "max_drawdown": report.max_drawdown,
        "var_95_1d": report.var_95_1d,
        "var_99_1d": report.var_99_1d,
        "correlation_matrix": report.correlation_matrix,
        "stress_scenarios": report.stress_scenarios,
        "warnings": report.warnings,
    }


def _serialize_valuation(p: Portfolio, val) -> dict[str, Any]:
    return {
        "id": p.id, "name": p.name, "base_currency": p.base_currency,
        "as_of": val.as_of.isoformat(),
        "cash_by_currency": {k: str(v) for k, v in val.cash_by_currency.items()},
        "cash_base": str(val.cash_base),
        "positions_value_base": str(val.positions_value_base),
        "equity_base": str(val.equity_base),
        "realized_pnl_base": str(val.realized_pnl_base),
        "unrealized_pnl_base": str(val.unrealized_pnl_base),
        "positions": [
            {
                "asset_canonical_id": pos.asset_canonical_id,
                "display_symbol": pos.display_symbol,
                "market": pos.market,
                "quantity": str(pos.quantity),
                "avg_cost": str(pos.avg_cost),
                "quote_currency": pos.quote_currency,
                "last_price": (str(pos.last_price) if pos.last_price is not None else None),
                "last_price_source": pos.last_price_source,
                "last_price_time": (
                    pos.last_price_time.isoformat() if pos.last_price_time else None
                ),
                "market_value_ccy": (
                    str(pos.market_value_ccy) if pos.market_value_ccy is not None else None
                ),
                "market_value_base": (
                    str(pos.market_value_base) if pos.market_value_base is not None else None
                ),
                "unrealized_pnl_ccy": (
                    str(pos.unrealized_pnl_ccy) if pos.unrealized_pnl_ccy is not None else None
                ),
                "unrealized_pnl_base": (
                    str(pos.unrealized_pnl_base) if pos.unrealized_pnl_base is not None else None
                ),
                "realized_pnl_ccy": str(pos.realized_pnl_ccy),
            }
            for pos in val.positions
        ],
        "fx_used": {f"{k[0]}->{k[1]}": str(v) for k, v in val.fx_used.items()},
        "warnings": val.warnings,
    }


# Silence unused
_ = TxKind
