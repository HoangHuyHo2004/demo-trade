"""Session endpoints (Phase 5.1 production auth)."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.core.auth import issue_session_token
from app.core.config import get_settings
from app.deps import CurrentUserDep, SessionDep, SettingsDep
from app.models.agent import AuditLog
from app.models.user import User

router = APIRouter()


@router.get("/me")
async def me(user: CurrentUserDep) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "oauth_provider": user.oauth_provider,
        "base_currency": user.base_currency,
        "locale": user.locale,
        "timezone": user.timezone,
    }


@router.post("/demo-login")
async def demo_login(
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> dict:
    """Issue a valid session token for the demo user.

    Only available when ``DEMO_MODE=true``. In production this returns
    404 so a rogue caller can't self-provision an account.
    """
    if not settings.demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not available")

    email = settings.api_demo_user_email
    user = (await session.execute(
        select(User).where(User.email == email)
    )).scalar_one_or_none()
    if user is None:
        user = User(email=email, display_name="Demo User",
                    oauth_provider="demo", oauth_account_id=email)
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = issue_session_token(
        subject=user.oauth_account_id or user.email,
        email=user.email,
        name=user.display_name or "Demo User",
        provider="demo",
    )
    _set_session_cookie(response, token, settings)

    session.add(AuditLog(
        actor=f"user:{user.id}", event="auth_demo_login",
        subject_type="user", subject_id=str(user.id),
        payload_json=json.dumps({"provider": "demo", "email": email}),
        created_at=datetime.now(UTC),
    ))
    await session.commit()
    return {"ok": True, "user_id": user.id}


@router.post("/logout")
async def logout(response: Response) -> dict:
    settings = get_settings()
    response.delete_cookie(settings.auth_cookie_name, path="/")
    return {"ok": True}


def _set_session_cookie(response: Response, token: str, settings) -> None:
    """Common cookie-set path so the flags are consistent everywhere."""
    is_prod = settings.app_env == "production"
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_max_age_s,
        httponly=True,
        secure=is_prod,          # dev/localhost allows non-HTTPS
        samesite="lax",
        path="/",
    )
