"""User preferences (spec §12 Settings page + §16 user_settings)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.deps import CurrentUserDep, SessionDep
from app.models.settings_alert import UserSettings

router = APIRouter()


class UserSettingsOut(BaseModel):
    email: str
    display_name: str
    base_currency: str
    locale: str
    timezone: str
    risk_display: str
    signal_horizon_default: str
    theme: str
    notifications_email: bool


class UserSettingsPatch(BaseModel):
    base_currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    locale: str | None = Field(None, pattern=r"^(en|vi)$")
    timezone: str | None = Field(None, min_length=1, max_length=64)
    risk_display: str | None = Field(
        None, pattern=r"^(BOTH|LEVEL_ONLY|SCORE_ONLY)$",
    )
    signal_horizon_default: str | None = Field(None, pattern=r"^(1D|5D|20D)$")
    theme: str | None = Field(None, pattern=r"^(light|dark|system)$")
    notifications_email: bool | None = None


async def _ensure_settings(session, user_id: int) -> UserSettings:
    row = (await session.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )).scalar_one_or_none()
    if row is None:
        row = UserSettings(user_id=user_id, updated_at=datetime.now(UTC))
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


@router.get("", response_model=UserSettingsOut)
async def get_settings(session: SessionDep, user: CurrentUserDep) -> UserSettingsOut:
    s = await _ensure_settings(session, user.id)
    return UserSettingsOut(
        email=user.email,
        display_name=user.display_name,
        base_currency=user.base_currency,
        locale=user.locale,
        timezone=user.timezone,
        risk_display=s.risk_display,
        signal_horizon_default=s.signal_horizon_default,
        theme=s.theme,
        notifications_email=s.notifications_email,
    )


@router.patch("", response_model=UserSettingsOut)
async def patch_settings(
    body: UserSettingsPatch, session: SessionDep, user: CurrentUserDep,
) -> UserSettingsOut:
    s = await _ensure_settings(session, user.id)
    # User-level (on the User row)
    if body.base_currency is not None:
        user.base_currency = body.base_currency
    if body.locale is not None:
        user.locale = body.locale
    if body.timezone is not None:
        # Extremely light validation — the frontend picker is our real UX guard.
        if any(c in body.timezone for c in " \t\n<>&"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="invalid timezone")
        user.timezone = body.timezone
    # UserSettings row
    if body.risk_display is not None:
        s.risk_display = body.risk_display
    if body.signal_horizon_default is not None:
        s.signal_horizon_default = body.signal_horizon_default
    if body.theme is not None:
        s.theme = body.theme
    if body.notifications_email is not None:
        s.notifications_email = body.notifications_email
    s.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    await session.refresh(s)
    return UserSettingsOut(
        email=user.email,
        display_name=user.display_name,
        base_currency=user.base_currency,
        locale=user.locale,
        timezone=user.timezone,
        risk_display=s.risk_display,
        signal_horizon_default=s.signal_horizon_default,
        theme=s.theme,
        notifications_email=s.notifications_email,
    )
