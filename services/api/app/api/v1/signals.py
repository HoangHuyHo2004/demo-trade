from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.deps import SessionDep
from app.models.asset import Asset
from app.services.signal_engine import calculate_signal, get_model

router = APIRouter()

_HORIZON_PATTERN = r"^(1D|5D|20D)$"


class SignalCalculateRequest(BaseModel):
    asset_canonical_id: str = Field(..., min_length=3, max_length=96)
    horizon: str = Field("5D", pattern=_HORIZON_PATTERN)
    model: str = Field("ensemble-v1", max_length=64)
    as_of: datetime | None = None


async def _load_asset(session, canonical_id: str) -> Asset:
    a = (await session.execute(
        select(Asset).where(Asset.canonical_id == canonical_id)
    )).scalar_one_or_none()
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="asset not found")
    return a


@router.get("/{asset_id:path}")
async def get_signal(
    asset_id: str,
    session: SessionDep,
    horizon: str = Query("5D", pattern=_HORIZON_PATTERN),
    model: str = Query("ensemble-v1", max_length=64),
) -> dict:
    asset = await _load_asset(session, asset_id)
    try:
        get_model(model)
    except KeyError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    result = await calculate_signal(
        session, asset=asset, horizon=horizon, model_code=model, persist=True,
    )
    return result.payload


@router.post("/calculate")
async def post_calculate(
    body: SignalCalculateRequest,
    session: SessionDep,
) -> dict:
    asset = await _load_asset(session, body.asset_canonical_id)
    try:
        get_model(body.model)
    except KeyError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    result = await calculate_signal(
        session, asset=asset, horizon=body.horizon,
        model_code=body.model, as_of=body.as_of, persist=True,
    )
    return result.payload
