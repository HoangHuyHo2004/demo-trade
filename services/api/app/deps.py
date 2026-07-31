"""FastAPI dependencies: session, current user, provider registry."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import InvalidSession, SessionClaims, verify_session_token
from app.core.config import Settings, get_settings
from app.db import get_session
from app.models.user import User
from app.providers.registry import ProviderRegistry, get_registry

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
RegistryDep = Annotated[ProviderRegistry, Depends(get_registry)]


async def _upsert_user_from_claims(
    session: AsyncSession, claims: SessionClaims,
) -> User:
    """Look up (or create) the user for a validated session token.

    First tries (oauth_provider, oauth_account_id); falls back to email.
    Creates the row on first login.
    """
    stmt = select(User).where(
        or_(
            (User.oauth_provider == claims.provider)
            & (User.oauth_account_id == claims.subject),
            User.email == claims.email,
        )
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        user = User(
            email=claims.email or f"{claims.subject}@{claims.provider}.local",
            display_name=claims.name or claims.email or claims.subject,
            oauth_provider=claims.provider,
            oauth_account_id=claims.subject,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        # Backfill oauth identity for existing users (e.g. the seeded demo user
        # signing in via GitHub for the first time). Never overwrite a
        # different provider identity — that would be an account takeover.
        changed = False
        if user.oauth_provider is None and user.oauth_account_id is None:
            user.oauth_provider = claims.provider
            user.oauth_account_id = claims.subject
            changed = True
        if claims.name and not user.display_name:
            user.display_name = claims.name
            changed = True
        if changed:
            await session.commit()
    return user


async def get_current_user(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    """Auth strategy:

    1. If the Auth.js session cookie is present, verify the HS256 JWT and
       upsert the user by (provider, subject).
    2. Otherwise, if ``DEMO_MODE=true``, fall back to the demo cookie
       flow that auto-creates the demo user. This branch is **disabled**
       in production.
    3. Otherwise, 401.
    """
    token = request.cookies.get(settings.auth_cookie_name)
    if token is None:
        # Support Bearer tokens too so backend-to-backend clients and
        # tests can authenticate without a browser.
        authz = request.headers.get("authorization", "")
        if authz.lower().startswith("bearer "):
            token = authz.split(" ", 1)[1].strip()

    if token:
        try:
            claims = verify_session_token(token)
        except InvalidSession as e:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, detail=f"invalid session: {e}",
            ) from e
        return await _upsert_user_from_claims(session, claims)

    if settings.demo_mode:
        # Backward-compat demo path. Deliberately absent in production.
        email = request.cookies.get("demo_user") or settings.api_demo_user_email
        existing = (await session.execute(
            select(User).where(User.email == email)
        )).scalar_one_or_none()
        if existing is not None:
            return existing
        user = User(email=email, display_name="Demo User")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="not authenticated")


CurrentUserDep = Annotated[User, Depends(get_current_user)]
