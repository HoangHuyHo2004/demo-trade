"""Job status polling (spec §14)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.deps import CurrentUserDep, SessionDep
from app.services.jobs import job_to_dict, load_job

router = APIRouter()


@router.get("/{job_id}")
async def get_job(
    job_id: str, session: SessionDep, user: CurrentUserDep,
) -> dict:
    job = await load_job(session, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="job not found")
    # In demo mode any signed-in user can read their own jobs. Cross-user
    # reads are refused. Anonymous jobs (user_id=None) are readable by
    # anyone in demo mode; enable a stricter check in production.
    if job.user_id is not None and job.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="not your job")
    return job_to_dict(job)
