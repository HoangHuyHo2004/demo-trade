import pytest

from app.models.asset import Asset


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready(client):
    r = await client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"


@pytest.mark.asyncio
async def test_markets_status_all_calendars(client):
    r = await client.get("/api/v1/markets/status")
    assert r.status_code == 200
    body = r.json()
    calendars = {row["calendar"] for row in body}
    assert {"XNYS", "XHOS", "XHNX", "UPCOM", "24x7"} <= calendars
    for row in body:
        assert row["state"] in {"OPEN", "CLOSED"}


@pytest.mark.asyncio
async def test_asset_search_and_quote(session, client):
    # Insert a minimal asset directly.
    a = Asset(
        canonical_id="EQUITY:US:NASDAQ:AAPL",
        asset_type="EQUITY", market="US", exchange_code="NASDAQ",
        symbol="AAPL", display_symbol="AAPL", name="Apple Inc.",
        quote_currency="USD", market_timezone="America/New_York", calendar="XNYS",
    )
    session.add(a)
    await session.commit()

    r = await client.get("/api/v1/assets/search", params={"q": "AAPL"})
    assert r.status_code == 200
    hits = r.json()
    assert any(x["canonical_id"] == "EQUITY:US:NASDAQ:AAPL" for x in hits)

    r = await client.get("/api/v1/prices/EQUITY:US:NASDAQ:AAPL/quote")
    assert r.status_code == 200
    q = r.json()
    assert q["asset_id"] == "EQUITY:US:NASDAQ:AAPL"
    assert q["currency"] == "USD"
    assert float(q["price"]) > 0
    assert q["source"] == "mock"


@pytest.mark.asyncio
async def test_bars_endpoint(session, client):
    session.add(Asset(
        canonical_id="CRYPTO:COINBASE:BTC-USD",
        asset_type="CRYPTO", market="COINBASE", exchange_code="COINBASE",
        symbol="BTC-USD", display_symbol="BTC/USD", name="Bitcoin",
        quote_currency="USD", base_asset="BTC", quote_asset="USD",
        market_timezone="UTC", calendar="24x7",
    ))
    await session.commit()

    r = await client.get(
        "/api/v1/prices/CRYPTO:COINBASE:BTC-USD/bars",
        params={"interval": "1d", "lookback_days": 60},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["interval"] == "1d"
    assert body["source"] == "mock"  # tests force mock-only
    assert "from_cache" in body
    assert body["from_cache"] is False  # first call → fresh fetch
    assert body["last_bar_time"] is not None
    assert body["last_ingest_time"] is not None
    assert len(body["bars"]) > 30

    # Second call should be served from cache (repository upserted the
    # bars on the first call).
    r2 = await client.get(
        "/api/v1/prices/CRYPTO:COINBASE:BTC-USD/bars",
        params={"interval": "1d", "lookback_days": 60},
    )
    assert r2.status_code == 200
    assert r2.json()["from_cache"] is True


@pytest.mark.asyncio
async def test_watchlist_flow(session, client):
    # Seed one asset first.
    a = Asset(
        canonical_id="EQUITY:VN:HOSE:VNM",
        asset_type="EQUITY", market="VN", exchange_code="HOSE",
        symbol="VNM", display_symbol="VNM", name="Vinamilk",
        quote_currency="VND", market_timezone="Asia/Ho_Chi_Minh", calendar="XHOS",
    )
    session.add(a)
    await session.commit()

    r = await client.post("/api/v1/watchlists", json={"name": "Test"})
    assert r.status_code == 201, r.text
    wl = r.json()

    r = await client.post(
        f"/api/v1/watchlists/{wl['id']}/items",
        json={"asset_canonical_id": "EQUITY:VN:HOSE:VNM"},
    )
    assert r.status_code == 201, r.text

    r = await client.get("/api/v1/watchlists")
    assert r.status_code == 200
    lists = r.json()
    assert len(lists) == 1
    assert lists[0]["items"][0]["asset"]["canonical_id"] == "EQUITY:VN:HOSE:VNM"


@pytest.mark.asyncio
async def test_providers_status(client):
    r = await client.get("/api/v1/providers/status")
    assert r.status_code == 200
    body = r.json()
    slugs = {p["slug"] for p in body}
    assert "mock" in slugs
    # In test env (USE_MOCK_PROVIDERS_ONLY=true) mock serves every market.
    mock_row = next(p for p in body if p["slug"] == "mock")
    assert set(mock_row["is_selected_for"]) >= {"US", "VN", "COINBASE"}
    for p in body:
        assert "markets" in p
        assert "is_selected_for" in p
