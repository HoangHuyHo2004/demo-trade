"""FastAPI dependencies: session, current user, provider registry."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db import get_session
from app.models.user import User
from app.providers.registry import ProviderRegistry, get_registry

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
RegistryDep = Annotated[ProviderRegistry, Depends(get_registry)]


async def get_current_user(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
) -> User:
    """Phase 1 mock auth: cookie 'demo_user' → resolve to seeded demo user.
    In demo mode we auto-create the demo user if the cookie is missing.
    """
    email = request.cookies.get("demo_user") or settings.api_demo_user_email
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        if settings.demo_mode:
            user = User(email=email, display_name="Demo User")
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
