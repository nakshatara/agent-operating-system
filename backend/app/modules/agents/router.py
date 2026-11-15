from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import (
    Principal,
    RequestContext,
    get_request_context,
    require_role,
)
from app.core.errors import AppError
from app.core.security import role_at_least
from app.modules.agents import service
from app.modules.agents.lifecycle import ACTIONS, ADMIN_ONLY_ACTIONS
from app.modules.agents.schemas import AgentCreate, AgentOut, AgentPage, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    data: AgentCreate,
    principal: Principal = Depends(require_role("operator")),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> AgentOut:
    agent = await service.create_agent(db, principal, ctx, data)
    await db.commit()
    return AgentOut.model_validate(agent)


@router.get("", response_model=AgentPage)
async def list_agents(
    status: str | None = None,
    readiness: str | None = Query(None, pattern="^(simulated|configured|live)$"),
    provider: str | None = None,
    q: str | None = Query(None, max_length=100),
    supervisor_agent_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
) -> AgentPage:
    rows, total = await service.list_agents(
        db,
        principal.organization_id,
        status=status,
        readiness=readiness,
        provider=provider,
        q=q,
        supervisor_agent_id=supervisor_agent_id,
        limit=limit,
        offset=offset,
    )
    return AgentPage(
        items=[AgentOut.model_validate(a) for a in rows], total=total, limit=limit, offset=offset
    )


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: uuid.UUID,
    principal: Principal = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
) -> AgentOut:
    return AgentOut.model_validate(await service.get_agent(db, principal.organization_id, agent_id))


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    data: AgentUpdate,
    principal: Principal = Depends(require_role("operator")),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> AgentOut:
    agent = await service.update_agent(db, principal, ctx, agent_id, data)
    await db.commit()
    return AgentOut.model_validate(agent)


@router.post("/{agent_id}/lifecycle/{action}", response_model=AgentOut)
async def lifecycle(
    agent_id: uuid.UUID,
    action: str,
    principal: Principal = Depends(require_role("operator")),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> AgentOut:
    if action not in ACTIONS:
        raise AppError(404, "unknown_action", f"Unknown lifecycle action '{action}'")
    if action in ADMIN_ONLY_ACTIONS and not role_at_least(principal.role, "admin"):
        raise AppError(403, "forbidden", f"Action '{action}' requires role 'admin' or higher")
    agent = await service.apply_lifecycle(db, principal, ctx, agent_id, action)
    await db.commit()
    return AgentOut.model_validate(agent)
