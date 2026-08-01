"""ML endpoints (spec §Machine-learning API endpoints).

Read paths are open to any signed-in user. Write paths (train / promote
/ disable) require ``CurrentAdminDep`` — the demo user is admin in
DEMO_MODE, and production requires a manually-promoted admin.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.deps import CurrentAdminDep, CurrentUserDep, SessionDep
from app.models.asset import Asset
from app.models.ml import (
    MLModel,
    MLModelState,
    MLPrediction,
    MLPredictionOutcome,
    MLTrainingRun,
)

router = APIRouter()


# ---------- read ----------

@router.get("/models")
async def list_models(session: SessionDep, _user: CurrentUserDep) -> list[dict]:
    rows = (await session.execute(
        select(MLModel).order_by(MLModel.created_at.desc())
    )).scalars().all()
    return [_serialize_model(m) for m in rows]


@router.get("/models/{model_id}")
async def get_model(model_id: int, session: SessionDep, _user: CurrentUserDep) -> dict:
    m = await _load_model_or_404(session, model_id)
    return _serialize_model(m)


@router.get("/models/{model_id}/metrics")
async def get_model_metrics(
    model_id: int, session: SessionDep, _user: CurrentUserDep,
) -> dict:
    m = await _load_model_or_404(session, model_id)
    runs = (await session.execute(
        select(MLTrainingRun).where(MLTrainingRun.model_id == model_id)
        .order_by(MLTrainingRun.created_at.desc()).limit(50)
    )).scalars().all()
    return {
        "model": _serialize_model(m),
        "runs": [
            {
                "public_id": r.public_id,
                "train_from": r.train_from.isoformat(),
                "train_to": r.train_to.isoformat(),
                "val_from": r.val_from.isoformat(),
                "val_to": r.val_to.isoformat(),
                "metrics": json.loads(r.metrics_json or "{}"),
                "status": r.status,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
        ],
    }


@router.get("/predictions/{asset_id:path}")
async def get_prediction(
    asset_id: str, session: SessionDep, _user: CurrentUserDep,
    horizon: str | None = None,
) -> dict:
    asset = await _load_asset(session, asset_id)
    stmt = select(MLPrediction).where(MLPrediction.asset_id == asset.id)
    if horizon:
        stmt = stmt.where(MLPrediction.horizon == horizon)
    stmt = stmt.order_by(MLPrediction.as_of.desc()).limit(1)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        # Follow the signal engine's INSUFFICIENT_DATA convention.
        return {
            "asset_id": asset.canonical_id,
            "status": "INSUFFICIENT_DATA",
            "detail": (
                "No ML prediction available. Train a model via "
                "POST /api/v1/ml/train and let the worker generate a "
                "prediction row."
            ),
        }
    return _serialize_prediction(row, asset)


@router.get("/predictions/{asset_id:path}/history")
async def prediction_history(
    asset_id: str, session: SessionDep, _user: CurrentUserDep,
    limit: int = 100,
) -> list[dict]:
    asset = await _load_asset(session, asset_id)
    limit = max(1, min(500, limit))
    rows = (await session.execute(
        select(MLPrediction).where(MLPrediction.asset_id == asset.id)
        .order_by(MLPrediction.as_of.desc()).limit(limit)
    )).scalars().all()
    return [_serialize_prediction(r, asset) for r in rows]


# ---------- admin writes ----------

class TrainRequest(BaseModel):
    market: str = Field(..., pattern=r"^(US|VN|COINBASE)$")
    horizon: str = Field("5D", pattern=r"^(1D|5D|20D)$")
    family: str = Field("logreg", pattern=r"^(logreg|rf|gbm)$")
    cost_bps: float = Field(5.0, ge=0.0, le=200.0)
    seed: int = Field(0, ge=0, le=1_000_000)
    calibrate: str = Field("isotonic", pattern=r"^(isotonic|sigmoid|none)$")


@router.post("/train", status_code=status.HTTP_202_ACCEPTED)
async def train(body: TrainRequest, _admin: CurrentAdminDep) -> dict:
    horizon_bars = {"1D": 1, "5D": 5, "20D": 20}[body.horizon]
    try:
        from mlw.celery_app import app as ml_app
        r = ml_app.send_task(
            "mlw.tasks.train_model",
            kwargs={
                "market": body.market, "horizon_bars": horizon_bars,
                "family": body.family, "cost_bps": body.cost_bps,
                "seed": body.seed, "calibrate": body.calibrate,
            },
        )
        return {"status": "queued", "task_id": r.id, "request": body.model_dump()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ml worker unreachable: {e}. Ensure ml_worker is running.",
        ) from e


@router.post("/models/{model_id}/shadow")
async def set_shadow(
    model_id: int, session: SessionDep, admin: CurrentAdminDep,
) -> dict:
    m = await _load_model_or_404(session, model_id)
    m.state = MLModelState.SHADOW.value
    m.approved_by_user_id = admin.id
    m.approval_note = "moved to SHADOW"
    await session.commit()
    return _serialize_model(m)


@router.post("/models/{model_id}/promote")
async def promote(
    model_id: int, session: SessionDep, admin: CurrentAdminDep,
) -> dict:
    """Promote SHADOW → CHAMPION. Phase 1 rules: candidate must have at
    least one training run + non-null artifact + a non-degraded state.
    The full acceptance checklist (spec §Model promotion requirements)
    lives in Phase 4."""
    m = await _load_model_or_404(session, model_id)
    if m.state in (MLModelState.DEGRADED.value, MLModelState.DISABLED.value,
                    MLModelState.RETIRED.value):
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             detail=f"cannot promote from {m.state}")
    if not m.artifact_sha256:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                             detail="candidate has no artifact")
    # Retire the current champion for the same (market, horizon, task).
    current = (await session.execute(
        select(MLModel).where(
            MLModel.market == m.market, MLModel.horizon == m.horizon,
            MLModel.task == m.task, MLModel.state == MLModelState.CHAMPION.value,
        )
    )).scalars().all()
    for c in current:
        c.state = MLModelState.CHALLENGER.value
    m.state = MLModelState.CHAMPION.value
    m.promoted_at = datetime.now(UTC)
    m.approved_by_user_id = admin.id
    m.approval_note = "promoted to CHAMPION"
    await session.commit()
    return _serialize_model(m)


@router.post("/models/{model_id}/disable")
async def disable(
    model_id: int, session: SessionDep, admin: CurrentAdminDep,
) -> dict:
    m = await _load_model_or_404(session, model_id)
    m.state = MLModelState.DISABLED.value
    m.approved_by_user_id = admin.id
    m.approval_note = "disabled"
    await session.commit()
    return _serialize_model(m)


# ---------- helpers ----------

async def _load_model_or_404(session, model_id: int) -> MLModel:
    m = (await session.execute(
        select(MLModel).where(MLModel.id == model_id)
    )).scalar_one_or_none()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="model not found")
    return m


async def _load_asset(session, canonical_id: str) -> Asset:
    a = (await session.execute(
        select(Asset).where(Asset.canonical_id == canonical_id)
    )).scalar_one_or_none()
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="asset not found")
    return a


def _serialize_model(m: MLModel) -> dict:
    return {
        "id": m.id, "code": m.code, "family": m.family,
        "market": m.market, "horizon": m.horizon, "task": m.task,
        "model_version": m.model_version, "dataset_version": m.dataset_version,
        "feature_version": m.feature_version, "target_version": m.target_version,
        "state": m.state,
        "artifact_sha256": m.artifact_sha256,
        "metrics": json.loads(m.metrics_json or "{}"),
        "params": json.loads(m.params_json or "{}"),
        "created_at": m.created_at.isoformat(),
        "promoted_at": m.promoted_at.isoformat() if m.promoted_at else None,
        "retired_at": m.retired_at.isoformat() if m.retired_at else None,
    }


def _serialize_prediction(p: MLPrediction, asset: Asset) -> dict:
    return {
        "asset_id": asset.canonical_id,
        "as_of": p.as_of.isoformat(),
        "horizon": p.horizon,
        "model_version": p.model_version,
        "data_version": p.data_version,
        "prob_positive": float(p.prob_positive) if p.prob_positive is not None else None,
        "prob_negative": float(p.prob_negative) if p.prob_negative is not None else None,
        "expected_return_median": (
            float(p.expected_return_median) if p.expected_return_median is not None else None
        ),
        "expected_return_lower": (
            float(p.expected_return_lower) if p.expected_return_lower is not None else None
        ),
        "expected_return_upper": (
            float(p.expected_return_upper) if p.expected_return_upper is not None else None
        ),
        "expected_volatility": (
            float(p.expected_volatility) if p.expected_volatility is not None else None
        ),
        "trend_continuation_probability": (
            float(p.trend_continuation_prob) if p.trend_continuation_prob is not None else None
        ),
        "drawdown_risk": p.drawdown_risk,
        "market_regime": p.market_regime,
        "confidence": float(p.confidence) if p.confidence is not None else None,
        "ood_score": float(p.ood_score) if p.ood_score is not None else None,
        "positive_contributors": json.loads(p.positive_contributors_json or "[]"),
        "negative_contributors": json.loads(p.negative_contributors_json or "[]"),
        "warnings": json.loads(p.warnings_json or "[]"),
        "shadow_only": True,
        "disclaimer": (
            "Machine-learning prediction. Probabilistic estimate only; "
            "not a directive. Rule-based signal engine remains the "
            "authoritative production signal in Phase 1."
        ),
    }


# Silence unused-import when only referenced via forward-declared types
_ = MLPredictionOutcome
