from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import (
    Principal,
    RequestContext,
    get_request_context,
    require_role,
)
from app.modules.agents import service as agents_service
from app.modules.runtime import service
from app.modules.runtime.schemas import ExecutionCreate, ExecutionOut, ExecutionPage

router = APIRouter(tags=["executions"])


@router.post("/agents/{agent_id}/executions", response_model=ExecutionOut, status_code=202)
async def create_execution(
    agent_id: uuid.UUID,
    data: ExecutionCreate,
    background: BackgroundTasks,
    principal: Principal = Depends(require_role("operator")),
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
) -> ExecutionOut:
    ex = await service.create_execution(db, principal, ctx, agent_id, data.prompt)
    await db.commit()
    background.add_task(service.run_execution, ex.id)
    return ExecutionOut.model_validate(ex)


@router.get("/agents/{agent_id}/executions", response_model=ExecutionPage)
async def list_agent_executions(
    agent_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
) -> ExecutionPage:
    await agents_service.get_agent(db, principal.organization_id, agent_id)
    rows, total = await service.list_executions(
        db, principal.organization_id, agent_id=agent_id, status=None, limit=limit, offset=offset
    )
    return ExecutionPage(
        items=[ExecutionOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/executions", response_model=ExecutionPage)
async def list_executions(
    status: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
) -> ExecutionPage:
    rows, total = await service.list_executions(
        db, principal.organization_id, agent_id=None, status=status, limit=limit, offset=offset
    )
    return ExecutionPage(
        items=[ExecutionOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/executions/{execution_id}", response_model=ExecutionOut)
async def get_execution(
    execution_id: uuid.UUID,
    principal: Principal = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
) -> ExecutionOut:
    return ExecutionOut.model_validate(
        await service.get_execution(db, principal.organization_id, execution_id)
    )
