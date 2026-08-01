"""ML worker Celery tasks.

- train_model: fit + calibrate + register a new model version. Writes
  ml_datasets (if new), ml_models, ml_training_runs. Model artifact
  saved to a local /var/lib/demo-trade/ml directory (path is
  configurable via ML_ARTIFACT_DIR); path + sha256 recorded on
  ml_models.
- generate_predictions: for every SHADOW/CHAMPION model, produce today's
  prediction row for every asset in the model's market and persist to
  ml_predictions.
- evaluate_outcomes: walk predictions whose horizon has expired,
  compute the outcome + calibration bucket + strategy P&L, and write
  ml_prediction_outcomes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mlw.celery_app import app
from mlw.models import TrainedModel, make_direction_model, sha256_of_file
from mlw.training import (
    features_matrix_from_rows,
    to_json_dict,
    train_direction_model,
)

log = logging.getLogger(__name__)

ARTIFACT_DIR = Path(os.getenv("ML_ARTIFACT_DIR", "/var/lib/demo-trade/ml"))


def _session_factory():
    """Fresh async session — the api's SessionLocal is bound to the api
    process's engine; the worker needs its own."""
    url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./demo.sqlite")
    engine = create_async_engine(url, echo=False, future=True)
    return async_sessionmaker(bind=engine, expire_on_commit=False)


# ---------- TRAIN ----------

@app.task(name="mlw.tasks.train_model", bind=True, max_retries=0)
def train_model(
    self, *,
    market: str, horizon_bars: int, family: str = "logreg",
    cost_bps: float = 5.0, from_time_iso: str | None = None,
    to_time_iso: str | None = None, seed: int = 0,
    calibrate: str = "isotonic",
) -> dict:
    return asyncio.run(_train_model_async(
        market=market, horizon_bars=horizon_bars, family=family,
        cost_bps=cost_bps, from_time_iso=from_time_iso,
        to_time_iso=to_time_iso, seed=seed, calibrate=calibrate,
    ))


async def _train_model_async(
    *, market: str, horizon_bars: int, family: str, cost_bps: float,
    from_time_iso: str | None, to_time_iso: str | None, seed: int,
    calibrate: str,
) -> dict:
    # Import lazily so the worker doesn't pull in the api's FastAPI stack
    # during boot.
    from app.ml.datasets import (
        BuildParams,
        build_dataset,
        make_walk_forward_folds,
    )
    from app.models.ml import (
        MLDataset,
        MLModel,
        MLModelState,
        MLTask,
        MLTrainingRun,
        MLTrainingStatus,
    )

    session_factory = _session_factory()
    async with session_factory() as session:
        params = BuildParams(
            market=market, horizon_bars=horizon_bars, interval="1d",
            cost_bps=cost_bps,
            from_time=(datetime.fromisoformat(from_time_iso) if from_time_iso else None),
            to_time=(datetime.fromisoformat(to_time_iso) if to_time_iso else None),
        )
        bench_by_market = {
            "US": "ETF:US:NYSE:SPY",
            "VN": "INDEX:VN:HOSE:VNINDEX",
            "COINBASE": "CRYPTO:COINBASE:BTC-USD",
        }
        table = await build_dataset(
            session, params, benchmark_canonical=bench_by_market.get(market),
        )
        if len(table.rows) < 200:
            return {"error": f"dataset too small ({len(table.rows)} rows)"}

        # Persist dataset row if not present
        dataset_row = (await session.execute(
            select(MLDataset).where(MLDataset.dataset_version == table.dataset_version)
        )).scalar_one_or_none()
        if dataset_row is None:
            dataset_row = MLDataset(
                dataset_version=table.dataset_version, market=market,
                universe_version="universe-v1", feature_version="features-v1",
                target_version="targets-v1",
                from_time=table.from_time or datetime.fromisoformat(table.rows[0]["bar_time"]),
                to_time=table.to_time or datetime.fromisoformat(table.rows[-1]["bar_time"]),
                row_count=len(table.rows),
                created_at=datetime.now(UTC),
                notes=f"assets={len(table.universe)}",
            )
            session.add(dataset_row)
            await session.commit()
            await session.refresh(dataset_row)

        # Register a new MLModel row (EXPERIMENTAL by default; SHADOW
        # promotion is a separate admin action).
        version = _version_stamp(family, market, horizon_bars, table.dataset_version)
        code = f"{market.lower()}-{MLTask.DIRECTION.value}-{family}-{version}"
        model_row = MLModel(
            code=code, family=family, market=market,
            horizon=_horizon_label(horizon_bars), task=MLTask.DIRECTION.value,
            model_version=version, dataset_version=table.dataset_version,
            feature_version="features-v1", target_version="targets-v1",
            state=MLModelState.EXPERIMENTAL.value,
            params_json=json.dumps({"cost_bps": cost_bps, "calibrate": calibrate,
                                     "seed": seed}, sort_keys=True),
            created_at=datetime.now(UTC),
        )
        session.add(model_row)
        await session.commit()
        await session.refresh(model_row)

        # ---- Walk-forward folds ----
        all_metrics: list[dict] = []
        row_times = [datetime.fromisoformat(r["bar_time"]) for r in table.rows]
        start = min(row_times)
        end = max(row_times)
        folds = make_walk_forward_folds(
            start=start, end=end,
            train_days=max(180, (end - start).days // 3),
            val_days=max(30, (end - start).days // 8),
            test_days=0, embargo_days=horizon_bars + 2,
        )
        if not folds:
            return {"error": "not enough history for a walk-forward fold"}

        final_model: TrainedModel | None = None
        last_metrics: dict | None = None
        for fold_idx, fold in enumerate(folds):
            train_rows = [r for r in table.rows
                          if fold.train_from <= datetime.fromisoformat(r["bar_time"]) < fold.train_to]
            val_rows = [r for r in table.rows
                        if fold.val_from <= datetime.fromisoformat(r["bar_time"]) < fold.val_to]
            X_train, y_train = features_matrix_from_rows(train_rows, table.feature_names)
            X_val, y_val = features_matrix_from_rows(val_rows, table.feature_names)
            if len(X_train) < 30 or len(X_val) < 10:
                log.warning("skip fold %d: n_train=%d n_val=%d",
                             fold_idx, len(X_train), len(X_val))
                continue
            try:
                m, mets, detail = train_direction_model(
                    family=family, X_train=X_train, y_train=y_train,
                    X_val=X_val, y_val=y_val,
                    feature_names=table.feature_names,
                    seed=seed, calibrate=calibrate,
                )
            except ValueError as e:
                log.warning("fold %d skipped: %s", fold_idx, e)
                continue

            # Persist a training-run row
            run = MLTrainingRun(
                public_id=f"trn_{uuid.uuid4().hex[:12]}",
                model_id=model_row.id, dataset_id=dataset_row.id,
                config_json=json.dumps(detail, sort_keys=True), seed=seed,
                train_from=fold.train_from, train_to=fold.train_to,
                val_from=fold.val_from, val_to=fold.val_to,
                metrics_json=to_json_dict(mets),
                status=MLTrainingStatus.COMPLETE.value,
                started_at=datetime.now(UTC), finished_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
            )
            session.add(run)
            all_metrics.append(mets.as_dict())
            last_metrics = mets.as_dict()
            final_model = m
        await session.commit()

        if final_model is None:
            model_row.state = MLModelState.DISABLED.value
            model_row.metrics_json = json.dumps({"error": "no successful folds"})
            await session.commit()
            return {"error": "no successful folds"}

        # Save artifact + record on the model row
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        artifact_path = ARTIFACT_DIR / f"{code}.joblib"
        sha = final_model.save(str(artifact_path))
        model_row.artifact_path = str(artifact_path)
        model_row.artifact_sha256 = sha
        model_row.metrics_json = json.dumps(_summarize_metrics(all_metrics), sort_keys=True)
        # All models start SHADOW so /predictions surfaces them but they
        # can't influence user-facing signals. Promotion to CHAMPION is
        # a separate admin action.
        model_row.state = MLModelState.SHADOW.value
        await session.commit()
        return {
            "model_id": model_row.id, "code": code, "state": model_row.state,
            "folds": len(all_metrics), "last_val_metrics": last_metrics,
        }


# ---------- PREDICT ----------

@app.task(name="mlw.tasks.generate_predictions", bind=True, max_retries=0)
def generate_predictions(self) -> str:
    return asyncio.run(_generate_predictions_async())


async def _generate_predictions_async() -> str:
    from app.ml.features import build_features, feature_names
    from app.models.asset import Asset
    from app.models.market_data import PriceBar
    from app.models.ml import MLModel, MLModelState, MLPrediction

    session_factory = _session_factory()
    async with session_factory() as session:
        models = (await session.execute(
            select(MLModel).where(MLModel.state.in_([
                MLModelState.SHADOW.value, MLModelState.CHAMPION.value,
            ]))
        )).scalars().all()
        written = 0
        for m in models:
            try:
                trained = TrainedModel.load(m.artifact_path)
            except Exception as e:  # noqa: BLE001
                log.warning("skip model %s: cannot load artifact (%s)", m.code, e)
                continue
            fnames = trained.feature_names or feature_names()
            assets = (await session.execute(
                select(Asset).where(Asset.market == m.market, Asset.is_active.is_(True))
            )).scalars().all()
            for a in assets:
                bars = (await session.execute(
                    select(PriceBar).where(
                        PriceBar.asset_id == a.id, PriceBar.interval == "1d",
                    ).order_by(PriceBar.bar_time.desc()).limit(400)
                )).scalars().all()
                bars = list(reversed(bars))
                if len(bars) < 60:
                    continue
                feats = build_features(
                    closes=[float(b.close) for b in bars],
                    highs=[float(b.high) for b in bars],
                    lows=[float(b.low) for b in bars],
                    volumes=[float(b.volume) for b in bars],
                )
                x = np.array([[feats.get(n, float("nan")) for n in fnames]])
                if np.isnan(x).any():
                    continue
                prob = float(trained.predict_proba(x)[0, 1])

                # Signed contributions when available (linear models);
                # tree-based models don't get a fabricated sign — see
                # docs/ml-explainability.md.
                pred_warnings = ["SHADOW model — does not influence user-facing signal"]
                signed = trained.signed_contributions(x[0], fnames)
                pos_contrib: list[tuple[str, float, float]] = []
                neg_contrib: list[tuple[str, float, float]] = []
                if signed is not None:
                    ranked = sorted(signed.items(), key=lambda kv: -abs(kv[1]))
                    pos_contrib = [
                        (n, float(x[0, fnames.index(n)]), c)
                        for n, c in ranked if c > 0
                    ][:5]
                    neg_contrib = [
                        (n, float(x[0, fnames.index(n)]), c)
                        for n, c in ranked if c < 0
                    ][:5]
                else:
                    imp = trained.feature_importance(fnames)
                    ranked_imp = sorted(imp.items(), key=lambda kv: -kv[1])[:5]
                    pos_contrib = [
                        (n, float(x[0, fnames.index(n)]), v) for n, v in ranked_imp
                    ]
                    pred_warnings.append(
                        "Tree-based model: factor magnitudes shown are unsigned "
                        "importance, not signed positive/negative contribution "
                        "(requires SHAP — not yet implemented)."
                    )

                pred = MLPrediction(
                    model_id=m.id, asset_id=a.id,
                    as_of=bars[-1].bar_time, horizon=m.horizon,
                    model_version=m.model_version, data_version=m.dataset_version or "unknown",
                    prob_positive=Decimal(f"{prob:.4f}"),
                    prob_negative=Decimal(f"{1 - prob:.4f}"),
                    confidence=Decimal(f"{abs(prob - 0.5) * 2:.4f}"),
                    positive_contributors_json=json.dumps([
                        {"feature": n, "value": v, "contribution": c}
                        for (n, v, c) in pos_contrib
                    ]),
                    negative_contributors_json=json.dumps([
                        {"feature": n, "value": v, "contribution": c}
                        for (n, v, c) in neg_contrib
                    ]),
                    warnings_json=json.dumps(pred_warnings),
                    created_at=datetime.now(UTC),
                )
                session.add(pred)
                written += 1
        await session.commit()
        return f"wrote {written} predictions for {len(models)} models"


# ---------- EVALUATE ----------

@app.task(name="mlw.tasks.evaluate_outcomes", bind=True, max_retries=0)
def evaluate_outcomes(self) -> str:
    return asyncio.run(_evaluate_outcomes_async())


async def _evaluate_outcomes_async() -> str:
    from app.models.market_data import PriceBar
    from app.models.ml import MLPrediction, MLPredictionOutcome

    session_factory = _session_factory()
    async with session_factory() as session:
        # Find predictions with no outcome row yet whose horizon has expired.
        stmt = select(MLPrediction).where(
            ~select(MLPredictionOutcome.id).where(
                MLPredictionOutcome.prediction_id == MLPrediction.id
            ).exists()
        )
        preds = (await session.execute(stmt)).scalars().all()
        wrote = 0
        for p in preds:
            horizon_days = {"1D": 1, "5D": 5, "20D": 20}.get(p.horizon, 5)
            target_time = p.as_of + timedelta(days=horizon_days)
            if target_time > datetime.now(UTC):
                continue
            # Load the close at as_of + horizon
            bar_rows = (await session.execute(
                select(PriceBar).where(
                    PriceBar.asset_id == p.asset_id,
                    PriceBar.interval == "1d",
                    PriceBar.bar_time >= target_time,
                ).order_by(PriceBar.bar_time.asc()).limit(1)
            )).scalars().all()
            if not bar_rows:
                continue
            c0_rows = (await session.execute(
                select(PriceBar).where(
                    PriceBar.asset_id == p.asset_id,
                    PriceBar.interval == "1d",
                    PriceBar.bar_time <= p.as_of,
                ).order_by(PriceBar.bar_time.desc()).limit(1)
            )).scalars().all()
            if not c0_rows:
                continue
            c0 = float(c0_rows[0].close)
            cH = float(bar_rows[0].close)
            if c0 <= 0 or cH <= 0:
                continue
            ret = (cH - c0) / c0
            direction = 1 if ret > 0 else (-1 if ret < 0 else 0)
            was_correct = None
            if p.prob_positive is not None:
                predicted_positive = float(p.prob_positive) >= 0.5
                was_correct = predicted_positive == (ret > 0)
            calib_bin = None
            if p.prob_positive is not None:
                pp = float(p.prob_positive)
                lo = int(pp * 10) * 10
                calib_bin = f"{lo/100:.2f}-{(lo+10)/100:.2f}"
            session.add(MLPredictionOutcome(
                prediction_id=p.id,
                actual_return=Decimal(f"{ret:.6f}"),
                actual_direction=direction,
                was_correct=was_correct,
                calibration_bucket=calib_bin,
                evaluated_at=datetime.now(UTC),
            ))
            wrote += 1
        await session.commit()
        return f"evaluated {wrote} predictions"


# ---------- helpers ----------

def _horizon_label(bars: int) -> str:
    return {1: "1D", 5: "5D", 20: "20D"}.get(bars, f"{bars}D")


def _version_stamp(family: str, market: str, horizon: int, dataset_version: str) -> str:
    return f"{family}-{market.lower()}-{horizon}D-{dataset_version[-8:]}"


def _summarize_metrics(all_metrics: list[dict]) -> dict:
    if not all_metrics:
        return {}
    keys = ["roc_auc", "pr_auc", "log_loss", "brier", "accuracy"]
    out = {"folds": len(all_metrics)}
    for k in keys:
        vals = [m[k] for m in all_metrics if m.get(k) is not None]
        if vals:
            out[f"{k}_mean"] = float(np.mean(vals))
            out[f"{k}_min"] = float(np.min(vals))
            out[f"{k}_max"] = float(np.max(vals))
    return out


# silence unused-import lint when running without a specific baseline model
_ = make_direction_model, sha256_of_file
