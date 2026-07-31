import pytest


@pytest.mark.asyncio
async def test_get_settings_creates_default_row(client):
    r = await client.get("/api/v1/settings")
    assert r.status_code == 200, r.text
    body = r.json()
    for k in ("email", "base_currency", "locale", "timezone",
              "risk_display", "signal_horizon_default", "theme",
              "notifications_email"):
        assert k in body
    assert body["risk_display"] == "BOTH"
    assert body["signal_horizon_default"] == "5D"


@pytest.mark.asyncio
async def test_patch_settings_persists(client):
    r = await client.patch("/api/v1/settings", json={
        "locale": "vi",
        "base_currency": "VND",
        "risk_display": "LEVEL_ONLY",
        "signal_horizon_default": "20D",
        "theme": "dark",
        "notifications_email": True,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["locale"] == "vi"
    assert body["base_currency"] == "VND"
    assert body["risk_display"] == "LEVEL_ONLY"
    assert body["signal_horizon_default"] == "20D"
    assert body["theme"] == "dark"
    assert body["notifications_email"] is True

    # Round-trip: GET returns the patched values.
    r2 = await client.get("/api/v1/settings")
    body2 = r2.json()
    assert body2["locale"] == "vi"
    assert body2["theme"] == "dark"


@pytest.mark.asyncio
async def test_patch_rejects_bad_enum(client):
    r = await client.patch("/api/v1/settings", json={"theme": "sepia"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_rejects_bad_currency(client):
    r = await client.patch("/api/v1/settings", json={"base_currency": "xx"})
    assert r.status_code == 422
