from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import Principal, require_role
from app.modules.dashboard import service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
root_router = APIRouter(tags=["health"])


@router.get("/summary")
async def get_summary(
    principal: Principal = Depends(require_role("viewer")), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await service.summary(db, principal.organization_id)


@root_router.get("/health")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@root_router.get("/ready")
async def readiness() -> JSONResponse:
    checks = await service.health()
    # Only PostgreSQL gates readiness; other stores degrade features but the API stays up.
    ready = checks["postgres"]["ok"]
    return JSONResponse(status_code=200 if ready else 503, content={"ready": ready, "checks": checks})
