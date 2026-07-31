"""Security headers, request-ID, and rate limiter tests."""
import pytest

from app.core.middleware import RateLimiter


@pytest.mark.asyncio
async def test_health_response_carries_security_headers(client):
    r = await client.get("/health")
    assert r.status_code == 200
    for h in ("x-content-type-options", "x-frame-options", "referrer-policy",
              "permissions-policy", "content-security-policy",
              "cross-origin-opener-policy", "cross-origin-resource-policy"):
        assert h in {k.lower(): v for k, v in r.headers.items()}


@pytest.mark.asyncio
async def test_request_id_header_returned(client):
    r = await client.get("/health")
    rid = r.headers.get("x-request-id")
    assert rid and len(rid) >= 8


@pytest.mark.asyncio
async def test_request_id_is_echoed_from_client(client):
    r = await client.get("/health", headers={"x-request-id": "trace-abc-1234"})
    assert r.headers["x-request-id"] == "trace-abc-1234"


@pytest.mark.asyncio
async def test_rate_limiter_blocks_beyond_limit():
    limiter = RateLimiter(limit=3, window_s=60.0, redis_url=None)
    key = "rl:test:client1"
    for _ in range(3):
        assert await limiter.allow(key) is True
    assert await limiter.allow(key) is False


@pytest.mark.asyncio
async def test_rate_limiter_isolates_by_key():
    limiter = RateLimiter(limit=1, window_s=60.0, redis_url=None)
    assert await limiter.allow("rl:a") is True
    assert await limiter.allow("rl:a") is False
    assert await limiter.allow("rl:b") is True   # different key still allowed


@pytest.mark.asyncio
async def test_write_endpoint_gets_rate_limited(client, monkeypatch):
    """Hit a cheap POST enough times to trip the '*' write bucket after
    monkeypatching its limit down to a tiny value.
    """
    from app.main import app
    # Locate the RateLimitMiddleware instance and swap its "*" limiter for
    # a limit-of-3 in-memory limiter. That way one test can prove the
    # middleware halts writes without waiting on 60+ real requests.
    rate_mw = None
    for mw in app.user_middleware:
        if mw.cls.__name__ == "RateLimitMiddleware":
            # user_middleware stores the class + kwargs; the built middleware
            # is on app.middleware_stack after the app starts. But since
            # ASGITransport(app=app) triggers build lazily, we replace via
            # a fresh mount below.
            rate_mw = mw
            break
    assert rate_mw is not None, "RateLimitMiddleware not installed"

    # Simplest way to test end-to-end: shrink the '*' rule via the
    # limiter's internal cache directly. The class holds `_limiters`,
    # but only after the middleware is constructed. We just call it 4
    # times and verify the 4th (or later) gets a 429 by inspecting
    # response history.
    from app.core.middleware import RateLimiter, RateLimitMiddleware
    RateLimitMiddleware._RULES = {"*": (3, 60.0)}
    # Rebuild the limiter map on the middleware instance
    # Force middleware rebuild by clearing the app's built stack.
    app.middleware_stack = None
    for mw_holder in app.user_middleware:
        if mw_holder.cls is RateLimitMiddleware:
            # nothing to do — recreating the app.middleware_stack on next
            # request will rebuild the middleware with the new class-level
            # _RULES.
            pass

    limit_hit = False
    for _ in range(6):
        r = await client.post("/api/v1/watchlists", json={"name": f"wl-{_}"})
        if r.status_code == 429:
            limit_hit = True
            break
    assert limit_hit, "expected 429 from rate limiter"
    # Also assert a request-id came back on the 429
    assert "x-request-id" in {k.lower(): v for k, v in r.headers.items()}

    # Reset the class-level rules for other tests
    RateLimitMiddleware._RULES = {"*": (300, 60.0)}
    app.middleware_stack = None
    _ = RateLimiter  # keep import used
