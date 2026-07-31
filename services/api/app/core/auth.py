"""Session-token auth.

The web app runs Auth.js v5 with a custom `jwt.encode/decode` pair that
issues **HS256-signed JWTs** (not the default JWE) using the shared
``AUTH_SECRET``. Every session cookie carries the standard Auth.js
claims (``sub``, ``email``, ``name``, ``exp``) plus a ``provider`` claim
indicating how the user authenticated.

This module verifies those tokens on the API side using PyJWT. The
verification result feeds ``app.deps.get_current_user``.

Rules:
  * Reject if the token isn't a valid HS256 JWT signed with the
    configured secret.
  * Reject if ``exp`` is missing, expired, or further in the future than
    ``auth_session_max_age_s`` (defense against a leaked secret being
    used to mint infinite-lived tokens).
  * Never accept a token when ``AUTH_SECRET`` is unset in production.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import get_settings

ALGO = "HS256"


class InvalidSession(Exception):
    pass


@dataclass(frozen=True)
class SessionClaims:
    subject: str          # stable per-user id from the identity provider
    email: str
    name: str
    provider: str         # "github" | "credentials" | "demo"
    issued_at: datetime
    expires_at: datetime


def issue_session_token(
    *,
    subject: str,
    email: str,
    name: str = "",
    provider: str = "demo",
    ttl_s: int | None = None,
) -> str:
    settings = get_settings()
    secret = settings.effective_auth_secret
    if not secret:
        raise InvalidSession("no AUTH_SECRET / API_SECRET_KEY configured")
    now = datetime.now(UTC)
    ttl = ttl_s or settings.auth_session_max_age_s
    payload: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "name": name,
        "provider": provider,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ALGO)


def verify_session_token(token: str) -> SessionClaims:
    settings = get_settings()
    secret = settings.effective_auth_secret
    if not secret:
        raise InvalidSession("no AUTH_SECRET configured")
    try:
        decoded = jwt.decode(
            token,
            secret,
            algorithms=[ALGO],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise InvalidSession("session expired") from e
    except jwt.InvalidTokenError as e:
        raise InvalidSession(f"invalid session token: {e}") from e

    # Belt-and-braces: reject unreasonably long-lived tokens even if the
    # signature checks out (e.g. an old client used a huge TTL, or a
    # stolen secret was used to mint one).
    now = datetime.now(UTC)
    exp = datetime.fromtimestamp(decoded["exp"], tz=UTC)
    if exp - now > timedelta(seconds=settings.auth_session_max_age_s + 60):
        raise InvalidSession("session TTL exceeds configured maximum")

    iat = datetime.fromtimestamp(decoded.get("iat") or now.timestamp(), tz=UTC)
    return SessionClaims(
        subject=str(decoded["sub"]),
        email=str(decoded.get("email") or ""),
        name=str(decoded.get("name") or ""),
        provider=str(decoded.get("provider") or "unknown"),
        issued_at=iat,
        expires_at=exp,
    )
