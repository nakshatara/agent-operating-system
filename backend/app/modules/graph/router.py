from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import Principal, RequestContext, get_request_context, require_role
from app.modules.audit import service as audit
from app.modules.graph import service

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("")
async def get_graph(principal: Principal = Depends(require_role("viewer"))) -> dict[str, Any]:
    return await service.get_graph(principal.organization_id)


@router.get("/agents/{agent_id}/hierarchy")
async def get_hierarchy(
    agent_id: uuid.UUID, principal: Principal = Depends(require_role("viewer"))
) -> dict[str, Any]:
    return await service.get_hierarchy(principal.organization_id, agent_id)


@router.post("/reconcile")
async def reconcile(
    principal: Principal = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    counts = await service.reconcile(db, principal.organization_id)
    audit.record_for(db, principal, ctx, "graph.reconcile", "organization", principal.organization_id, after=counts)
    await db.commit()
    return {"reconciled": counts}
