"""ML API: admin gating, INSUFFICIENT_DATA fallback, model lifecycle."""
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models.asset import Asset
from app.models.ml import MLModel, MLModelState
from app.models.user import User


async def _seed_asset(session, canonical="EQUITY:US:NASDAQ:AAPL") -> Asset:
    a = Asset(
        canonical_id=canonical, asset_type="EQUITY", market="US",
        exchange_code="NASDAQ", symbol="AAPL", display_symbol="AAPL",
        name="Apple", quote_currency="USD",
        market_timezone="America/New_York", calendar="XNYS",
    )
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


async def _seed_model(session, *, market="US", state=MLModelState.SHADOW.value) -> MLModel:
    m = MLModel(
        code=f"test-{market.lower()}-logreg-0.1.0-{state.lower()}",
        family="logreg", market=market, horizon="5D", task="direction",
        model_version="0.1.0", feature_version="features-v1",
        target_version="targets-v1", state=state,
        created_at=datetime.now(UTC),
    )
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


@pytest.mark.asyncio
async def test_prediction_returns_insufficient_data_when_none_exists(session, client):
    await _seed_asset(session)
    r = await client.get("/api/v1/ml/predictions/EQUITY:US:NASDAQ:AAPL")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "INSUFFICIENT_DATA"


@pytest.mark.asyncio
async def test_list_models_requires_auth(session, client):
    await _seed_model(session)
    # The test client auto-provisions the demo user via DEMO_MODE, so this
    # should succeed (200), not 401 — confirms the read path works for a
    # normal signed-in (non-admin) user.
    r = await client.get("/api/v1/ml/models")
    assert r.status_code == 200
    models = r.json()
    assert any(m["family"] == "logreg" for m in models)


@pytest.mark.asyncio
async def test_train_requires_admin(session, client):
    # The seeded demo user in tests is NOT marked admin by default (only
    # scripts/seed.py does that, which tests don't run) — verify a
    # non-admin gets 403.
    r = await client.post("/api/v1/ml/train", json={
        "market": "US", "horizon": "5D", "family": "logreg",
    })
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_promote_requires_admin(session, client):
    m = await _seed_model(session)
    r = await client.post(f"/api/v1/ml/models/{m.id}/promote")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_disable_requires_admin(session, client):
    m = await _seed_model(session)
    r = await client.post(f"/api/v1/ml/models/{m.id}/disable")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_promote_shadow_to_champion(session, client):
    # Mark the demo user admin directly (simulating what seed.py does).
    from app.core.config import get_settings
    settings = get_settings()
    user = (await session.execute(
        select(User).where(User.email == settings.api_demo_user_email)
    )).scalar_one_or_none()
    if user is None:
        user = User(email=settings.api_demo_user_email, display_name="Demo", is_admin=True)
        session.add(user)
    else:
        user.is_admin = True
    await session.commit()

    m = await _seed_model(session, state=MLModelState.SHADOW.value)
    m.artifact_sha256 = "deadbeef"  # promote requires a saved artifact
    await session.commit()

    r = await client.post(f"/api/v1/ml/models/{m.id}/promote")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "CHAMPION"


@pytest.mark.asyncio
async def test_promote_without_artifact_rejected(session, client):
    from app.core.config import get_settings
    settings = get_settings()
    user = (await session.execute(
        select(User).where(User.email == settings.api_demo_user_email)
    )).scalar_one_or_none()
    if user is None:
        user = User(email=settings.api_demo_user_email, display_name="Demo", is_admin=True)
        session.add(user)
    else:
        user.is_admin = True
    await session.commit()

    m = await _seed_model(session, state=MLModelState.SHADOW.value)
    # no artifact_sha256 set
    r = await client.post(f"/api/v1/ml/models/{m.id}/promote")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_promote_retires_previous_champion(session, client):
    from app.core.config import get_settings
    settings = get_settings()
    user = (await session.execute(
        select(User).where(User.email == settings.api_demo_user_email)
    )).scalar_one_or_none()
    if user is None:
        user = User(email=settings.api_demo_user_email, display_name="Demo", is_admin=True)
        session.add(user)
    else:
        user.is_admin = True
    await session.commit()

    old_champ = await _seed_model(session, state=MLModelState.CHAMPION.value)
    new_candidate = await _seed_model(session, state=MLModelState.SHADOW.value)
    new_candidate.artifact_sha256 = "cafebabe"
    await session.commit()

    r = await client.post(f"/api/v1/ml/models/{new_candidate.id}/promote")
    assert r.status_code == 200
    await session.refresh(old_champ)
    assert old_champ.state == "CHALLENGER"


@pytest.mark.asyncio
async def test_get_unknown_model_404s(session, client):
    r = await client.get("/api/v1/ml/models/999999")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_train_endpoint_202_or_503_when_broker_unreachable(session, client):
    """We don't run a live celery broker in tests, so this should
    gracefully 503 rather than hang or 500."""
    from app.core.config import get_settings
    settings = get_settings()
    user = (await session.execute(
        select(User).where(User.email == settings.api_demo_user_email)
    )).scalar_one_or_none()
    if user is None:
        user = User(email=settings.api_demo_user_email, display_name="Demo", is_admin=True)
        session.add(user)
    else:
        user.is_admin = True
    await session.commit()

    r = await client.post("/api/v1/ml/train", json={
        "market": "US", "horizon": "5D", "family": "logreg",
    })
    assert r.status_code in (202, 503)
