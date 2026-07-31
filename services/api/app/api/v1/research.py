"""Canonical per-asset research — a one-shot GET that runs the agent
with a fixed prompt and returns the structured summary.

Handy for the asset detail page's "Research" panel where a chat isn't
required.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.agent.orchestrator import Budget, run_agent_turn
from app.deps import CurrentUserDep, SessionDep
from app.models.asset import Asset

router = APIRouter()


@router.get("/{asset_id:path}")
async def get_research(
    asset_id: str, session: SessionDep, user: CurrentUserDep,
) -> dict:
    asset = (await session.execute(
        select(Asset).where(Asset.canonical_id == asset_id)
    )).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="asset not found")
    prompt = (
        f"Provide a structured research summary for {asset.canonical_id} "
        f"({asset.display_symbol} — {asset.name}). Use the quantitative "
        f"tools to fetch the current quote and the current signal at the "
        f"5D horizon. Do not invent news or filings; abstain honestly on "
        f"anything you cannot verify from a tool."
    )
    result = await run_agent_turn(
        session, user_prompt=prompt, user_id=user.id,
        asset_hint_canonical_id=asset.canonical_id, budget=Budget(),
    )
    return {
        "run_id": result.run_id,
        "status": result.status,
        "response": result.response.model_dump(mode="json"),
    }
