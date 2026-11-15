from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Principal, RequestContext
from app.modules.audit.models import AuditLog


def record(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | uuid.UUID | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ctx: RequestContext | None = None,
) -> AuditLog:
    """Stage an audit row in the caller's transaction (commits atomically with the change)."""
    row = AuditLog(
        id=uuid.uuid4(),
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        before=before,
        after=after,
        ip=ctx.ip if ctx else None,
        trace_id=ctx.trace_id if ctx else None,
    )
    db.add(row)
    return row


def record_for(
    db: AsyncSession,
    principal: Principal,
    ctx: RequestContext,
    action: str,
    resource_type: str,
    resource_id: str | uuid.UUID | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> AuditLog:
    return record(
        db,
        organization_id=principal.organization_id,
        actor_user_id=principal.user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before=before,
        after=after,
        ctx=ctx,
    )


async def list_logs(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    actor_user_id: uuid.UUID | None,
    since: datetime | None,
    until: datetime | None,
    limit: int,
    offset: int,
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog).where(AuditLog.organization_id == organization_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if since:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until:
        stmt = stmt.where(AuditLog.created_at <= until)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        (await db.execute(stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return list(rows), int(total)
