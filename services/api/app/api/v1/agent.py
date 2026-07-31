from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.orchestrator import Budget, run_agent_turn
from app.agent.schemas import ResearchResponse
from app.deps import CurrentUserDep, SessionDep
from app.models.agent import AgentRun
from app.models.asset import Asset

router = APIRouter()


class AgentChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    asset_canonical_id: str | None = Field(None, min_length=3, max_length=96)
    max_tool_calls: int | None = Field(None, ge=1, le=20)
    max_output_tokens: int | None = Field(None, ge=64, le=4000)


class AgentChatResponse(BaseModel):
    run_id: int
    status: str
    response: ResearchResponse


@router.post("/chat", response_model=AgentChatResponse)
async def chat(
    body: AgentChatRequest,
    session: SessionDep,
    user: CurrentUserDep,
) -> AgentChatResponse:
    if body.asset_canonical_id:
        exists = (await session.execute(
            select(Asset).where(Asset.canonical_id == body.asset_canonical_id)
        )).scalar_one_or_none()
        if exists is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="asset not found")

    budget = Budget()
    if body.max_tool_calls is not None:
        budget.max_tool_calls = body.max_tool_calls
    if body.max_output_tokens is not None:
        budget.max_output_tokens = body.max_output_tokens

    result = await run_agent_turn(
        session, user_prompt=body.prompt, user_id=user.id,
        asset_hint_canonical_id=body.asset_canonical_id,
        budget=budget,
    )
    return AgentChatResponse(
        run_id=result.run_id, status=result.status, response=result.response,
    )


@router.get("/runs/{run_id}")
async def get_run(run_id: int, session: SessionDep, user: CurrentUserDep) -> dict:
    run = (await session.execute(
        select(AgentRun).where(AgentRun.id == run_id)
    )).scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="run not found")
    # In demo mode any signed-in user can read any run they created.
    # A production build gates by user_id + admin role.
    if run.user_id is not None and run.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="not your run")
    return {
        "id": run.id,
        "status": run.status,
        "llm_provider": run.llm_provider,
        "llm_model": run.llm_model,
        "tool_call_count": run.tool_call_count,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "cost_usd_micro": run.cost_usd_micro,
        "wallclock_ms": run.wallclock_ms,
        "response": run.response_json,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }
