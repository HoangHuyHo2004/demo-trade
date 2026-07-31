from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.deps import RegistryDep

router = APIRouter()


class ProviderStatusOut(BaseModel):
    slug: str
    kind: str
    status: str
    message: str


@router.get("/status", response_model=list[ProviderStatusOut])
async def providers_status(registry: RegistryDep) -> list[ProviderStatusOut]:
    return [
        ProviderStatusOut(slug=p.slug, kind=p.kind, status=p.status, message=p.message)
        for p in registry.list_status()
    ]
