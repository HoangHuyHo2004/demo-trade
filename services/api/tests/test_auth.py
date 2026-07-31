"""Session JWT verification + auth endpoints."""
import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.auth import (
    InvalidSession,
    issue_session_token,
    verify_session_token,
)
from app.core.config import get_settings

# ---------- pure verifier ----------

def test_issue_then_verify_roundtrip():
    tok = issue_session_token(
        subject="gh|123", email="u@example.com", name="Test User",
        provider="github",
    )
    claims = verify_session_token(tok)
    assert claims.subject == "gh|123"
    assert claims.email == "u@example.com"
    assert claims.name == "Test User"
    assert claims.provider == "github"
    assert claims.expires_at > claims.issued_at


def test_verify_rejects_wrong_secret():
    tok = issue_session_token(subject="a", email="a@x", name="A", provider="demo")
    settings = get_settings()
    bad = jwt.encode({"sub": "a", "email": "a@x", "exp": int(time.time()) + 3600},
                     "not-the-real-secret-not-the-real-secret", algorithm="HS256")
    with pytest.raises(InvalidSession):
        verify_session_token(bad)
    # Sanity: the real token still verifies.
    verify_session_token(tok)
    _ = settings


def test_verify_rejects_expired():
    settings = get_settings()
    payload = {
        "sub": "a", "email": "a@x", "provider": "demo",
        "iat": int(time.time()) - 3600,
        "exp": int(time.time()) - 5,   # already expired
    }
    tok = jwt.encode(payload, settings.effective_auth_secret, algorithm="HS256")
    with pytest.raises(InvalidSession, match="expired"):
        verify_session_token(tok)


def test_verify_rejects_missing_exp():
    settings = get_settings()
    tok = jwt.encode({"sub": "a"}, settings.effective_auth_secret, algorithm="HS256")
    with pytest.raises(InvalidSession):
        verify_session_token(tok)


def test_verify_rejects_too_far_future_ttl():
    """A token with `exp` beyond max_age (+ 60s slack) must be rejected."""
    settings = get_settings()
    payload = {
        "sub": "a", "email": "a@x", "provider": "demo",
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.auth_session_max_age_s + 3600,
    }
    tok = jwt.encode(payload, settings.effective_auth_secret, algorithm="HS256")
    with pytest.raises(InvalidSession, match="TTL"):
        verify_session_token(tok)


# ---------- HTTP-level ----------

@pytest.mark.asyncio
async def test_me_requires_auth_when_demo_disabled(client, monkeypatch):
    from app.core import config as cfg_mod
    orig = cfg_mod.get_settings()
    monkeypatch.setattr(orig, "demo_mode", False, raising=False)
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
    monkeypatch.setattr(orig, "demo_mode", True, raising=False)


@pytest.mark.asyncio
async def test_demo_login_issues_valid_cookie_and_me_recognizes_it(client):
    r = await client.post("/api/v1/auth/demo-login")
    assert r.status_code == 200, r.text
    settings = get_settings()
    assert settings.auth_cookie_name in r.cookies
    token = r.cookies[settings.auth_cookie_name]
    claims = verify_session_token(token)
    assert claims.provider == "demo"

    r2 = await client.get("/api/v1/auth/me")
    assert r2.status_code == 200
    body = r2.json()
    assert body["email"] == settings.api_demo_user_email
    assert body["oauth_provider"] in {"demo", None}


@pytest.mark.asyncio
async def test_bearer_token_works(client):
    """Backend clients can pass the JWT as a Bearer header instead of a cookie."""
    tok = issue_session_token(
        subject="tester", email="tester@example.com", name="Tester",
        provider="github",
    )
    r = await client.get(
        "/api/v1/auth/me",
        headers={"authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "tester@example.com"
    assert body["oauth_provider"] == "github"


@pytest.mark.asyncio
async def test_invalid_cookie_rejected(client):
    settings = get_settings()
    r = await client.get(
        "/api/v1/auth/me",
        cookies={settings.auth_cookie_name: "not.a.jwt"},
    )
    # Explicit bad cookie must 401, even if DEMO_MODE would otherwise
    # auto-provision a user — we don't want to hide auth failures.
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_cookie(client):
    await client.post("/api/v1/auth/demo-login")
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    # Set-Cookie should carry a deletion (Max-Age=0 or expires in the past)
    set_cookie = r.headers.get("set-cookie", "")
    assert "demo-trade.session" in set_cookie
    assert ("Max-Age=0" in set_cookie or "expires=" in set_cookie.lower())


# Suppress unused import warning when only used above
_ = datetime, timedelta, UTC
