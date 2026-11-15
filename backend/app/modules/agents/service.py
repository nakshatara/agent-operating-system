from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import utcnow
from app.core.deps import Principal, RequestContext
from app.core.errors import AppError, not_found
from app.modules.agents.hierarchy import would_create_cycle
from app.modules.agents.lifecycle import (
    EDITABLE_STATUSES,
    InvalidTransition,
    next_status,
)
from app.modules.agents.models import Agent
from app.modules.agents.readiness import compute_readiness
from app.modules.agents.schemas import AgentCreate, AgentUpdate
from app.modules.audit import service as audit
from app.modules.events.envelope import EventType
from app.modules.events.outbox import emit
from app.modules.model_gateway import registry

ACTION_EVENT = {
    "activate": EventType.AGENT_ACTIVATED,
    "pause": EventType.AGENT_PAUSED,
    "resume": EventType.AGENT_RESUMED,
    "disable": EventType.AGENT_DISABLED,
    "restart": EventType.AGENT_RESTARTED,
    "archive": EventType.AGENT_ARCHIVED,
    "terminate": EventType.AGENT_TERMINATED,
}

CONFIG_FIELDS = (
    "name",
    "role",
    "description",
    "system_instructions",
    "objectives",
    "provider",
    "model",
    "autonomy_level",
    "supervisor_agent_id",
    "execution_mode",
)


def agent_snapshot(agent: Agent) -> dict:
    """Event / graph / audit summary of an agent (no system instructions: they may be sensitive)."""
    return {
        "id": str(agent.id),
        "organization_id": str(agent.organization_id),
        "name": agent.name,
        "role": agent.role,
        "provider": agent.provider,
        "model": agent.model,
        "autonomy_level": agent.autonomy_level,
        "supervisor_agent_id": str(agent.supervisor_agent_id) if agent.supervisor_agent_id else None,
        "execution_mode": agent.execution_mode,
        "status": agent.status,
        "version": agent.version,
        "readiness": compute_readiness(agent.execution_mode, agent.provider),
    }


def _validate_model_choice(provider: str, model: str, execution_mode: str) -> None:
    if registry.find_model(provider, model) is None:
        raise AppError(422, "invalid_model", f"Unsupported provider/model: {provider}/{model}")
    if execution_mode == "live" and provider == "simulated":
        raise AppError(422, "invalid_model", "Live mode requires a real provider (anthropic or openai)")


async def _validate_supervisor(
    db: AsyncSession,
    organization_id: uuid.UUID,
    agent_id: uuid.UUID | None,
    supervisor_id: uuid.UUID | None,
) -> None:
    if supervisor_id is None:
        return
    if agent_id is not None and supervisor_id == agent_id:
        raise AppError(422, "supervisor_cycle", "An agent cannot supervise itself")
    supervisor = await db.scalar(
        select(Agent).where(Agent.id == supervisor_id, Agent.organization_id == organization_id)
    )
    # Same error for "missing" and "belongs to another tenant" so ids can't be probed.
    if supervisor is None:
        raise AppError(422, "invalid_supervisor", "Supervisor agent not found in your organization")
    if supervisor.status in ("terminated", "archived"):
        raise AppError(422, "invalid_supervisor", f"Supervisor agent is {supervisor.status}")
    if agent_id is not None:
        rows = await db.execute(
            select(Agent.id, Agent.supervisor_agent_id).where(Agent.organization_id == organization_id)
        )
        parent_of = {r[0]: r[1] for r in rows.all()}
        if would_create_cycle(agent_id, supervisor_id, parent_of):
            raise AppError(422, "supervisor_cycle", "This supervisor assignment would create a cycle")


async def get_agent(
    db: AsyncSession, organization_id: uuid.UUID, agent_id: uuid.UUID, *, for_update: bool = False
) -> Agent:
    stmt = select(Agent).where(Agent.id == agent_id, Agent.organization_id == organization_id)
    if for_update:
        stmt = stmt.with_for_update()
    agent = await db.scalar(stmt)
    if agent is None:
        raise not_found("Agent")
    return agent


async def create_agent(
    db: AsyncSession, principal: Principal, ctx: RequestContext, data: AgentCreate
) -> Agent:
    org_id = principal.organization_id
    _validate_model_choice(data.provider, data.model, data.execution_mode)
    await _validate_supervisor(db, org_id, None, data.supervisor_agent_id)
    if await db.scalar(select(Agent.id).where(Agent.organization_id == org_id, Agent.name == data.name)):
        raise AppError(409, "agent_name_taken", "An agent with this name already exists")
    agent = Agent(
        id=uuid.uuid4(),
        organization_id=org_id,
        name=data.name,
        role=data.role,
        description=data.description,
        system_instructions=data.system_instructions,
        objectives=data.objectives,
        provider=data.provider,
        model=data.model,
        autonomy_level=data.autonomy_level,
        supervisor_agent_id=data.supervisor_agent_id,
        execution_mode=data.execution_mode,
        status="draft",
        version=1,
        created_by=principal.user_id,
    )
    db.add(agent)
    await db.flush()
    snap = agent_snapshot(agent)
    emit(db, EventType.AGENT_CREATED, org_id, {"agent": snap}, trace_id=ctx.trace_id)
    audit.record_for(db, principal, ctx, "agent.create", "agent", agent.id, after=snap)
    return agent


async def list_agents(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    status: str | None,
    readiness: str | None,
    provider: str | None,
    q: str | None,
    supervisor_agent_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Agent], int]:
    stmt = select(Agent).where(Agent.organization_id == organization_id)
    if status:
        stmt = stmt.where(Agent.status == status)
    if provider:
        stmt = stmt.where(Agent.provider == provider)
    if supervisor_agent_id:
        stmt = stmt.where(Agent.supervisor_agent_id == supervisor_agent_id)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(Agent.name.ilike(f"%{escaped}%", escape="\\"))
    if readiness:
        keyed = [p for p in registry.REAL_PROVIDERS if settings.provider_api_key(p)]
        if readiness == "simulated":
            stmt = stmt.where(Agent.execution_mode == "simulated")
        elif readiness == "live":
            stmt = stmt.where(Agent.execution_mode == "live", Agent.provider.in_(keyed))
        elif readiness == "configured":
            stmt = stmt.where(Agent.execution_mode == "live", Agent.provider.not_in(keyed))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await db.execute(stmt.order_by(Agent.created_at.desc()).limit(limit).offset(offset))
    return list(rows.scalars().all()), int(total)


async def update_agent(
    db: AsyncSession,
    principal: Principal,
    ctx: RequestContext,
    agent_id: uuid.UUID,
    data: AgentUpdate,
) -> Agent:
    org_id = principal.organization_id
    agent = await get_agent(db, org_id, agent_id, for_update=True)
    if agent.status not in EDITABLE_STATUSES:
        raise AppError(409, "agent_not_editable", f"Agent is {agent.status} and cannot be edited")
    changes = data.model_dump(exclude_unset=True)
    # name/role etc. may not be nulled out; supervisor_agent_id may (explicit null clears it).
    changes = {
        k: v for k, v in changes.items() if k in CONFIG_FIELDS and (v is not None or k == "supervisor_agent_id")
    }
    changed = {k: v for k, v in changes.items() if getattr(agent, k) != v}
    if not changed:
        return agent

    provider = changed.get("provider", agent.provider)
    model = changed.get("model", agent.model)
    mode = changed.get("execution_mode", agent.execution_mode)
    if {"provider", "model", "execution_mode"} & changed.keys():
        _validate_model_choice(provider, model, mode)
    if "supervisor_agent_id" in changed:
        await _validate_supervisor(db, org_id, agent.id, changed["supervisor_agent_id"])
    if "name" in changed:
        taken = await db.scalar(
            select(Agent.id).where(
                Agent.organization_id == org_id, Agent.name == changed["name"], Agent.id != agent.id
            )
        )
        if taken:
            raise AppError(409, "agent_name_taken", "An agent with this name already exists")

    before = {k: _jsonable(getattr(agent, k)) for k in changed}
    for k, v in changed.items():
        setattr(agent, k, v)
    agent.version += 1
    agent.updated_at = utcnow()
    await db.flush()
    after = {k: _jsonable(getattr(agent, k)) for k in changed}
    emit(db, EventType.AGENT_UPDATED, org_id, {"agent": agent_snapshot(agent), "changed": sorted(changed)}, trace_id=ctx.trace_id)
    audit.record_for(db, principal, ctx, "agent.update", "agent", agent.id, before=before, after=after)
    return agent


def _jsonable(value):
    return str(value) if isinstance(value, uuid.UUID) else value


async def apply_lifecycle(
    db: AsyncSession,
    principal: Principal,
    ctx: RequestContext,
    agent_id: uuid.UUID,
    action: str,
) -> Agent:
    org_id = principal.organization_id
    agent = await get_agent(db, org_id, agent_id, for_update=True)
    old = agent.status
    try:
        new = next_status(old, action)
    except InvalidTransition as exc:
        raise AppError(409, "invalid_transition", str(exc)) from None
    agent.status = new
    agent.updated_at = utcnow()
    await db.flush()
    payload = {"agent": agent_snapshot(agent), "action": action, "from_status": old, "to_status": new}
    emit(db, ACTION_EVENT[action], org_id, payload, trace_id=ctx.trace_id)
    audit.record_for(
        db, principal, ctx, f"agent.{action}", "agent", agent.id, before={"status": old}, after={"status": new}
    )
    return agent
