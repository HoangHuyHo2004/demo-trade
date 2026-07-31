from __future__ import annotations

from fastapi import APIRouter

from app.services.market_status import MarketStatus, all_statuses

router = APIRouter()


@router.get("/status", response_model=list[MarketStatus])
async def markets_status() -> list[MarketStatus]:
    return all_statuses()
