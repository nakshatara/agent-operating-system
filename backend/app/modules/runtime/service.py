from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_sessionmaker, utcnow
from app.core.deps import Principal, RequestContext
from app.core.errors import AppError, not_found
from app.modules.agents import service as agents_service
from app.modules.agents.lifecycle import can_execute
from app.modules.agents.models import Agent
from app.modules.agents.readiness import compute_readiness
from app.modules.audit import service as audit
from app.modules.events.envelope import EventType
from app.modules.events.outbox import emit
from app.modules.model_gateway import registry
from app.modules.model_gateway.base import ModelRequest, ProviderError
from app.modules.model_gateway.gateway import get_provider
from app.modules.runtime.models import Execution

logger = logging.getLogger(__name__)


def build_system_prompt(agent: Agent) -> str:
    """Operator-authored configuration only. The user prompt is passed separately as the user turn."""
    parts = [agent.system_instructions.strip()] if agent.system_instructions.strip() else []
    parts.append(f"You are '{agent.name}', acting in the role: {agent.role}.")
    if agent.objectives:
        parts.append("Objectives:\n" + "\n".join(f"- {o}" for o in agent.objectives))
    return "\n\n".join(parts)


def execution_payload(ex: Execution) -> dict:
    """Event payload: metadata only (no prompt/output content)."""
    return {
        "execution": {
            "id": str(ex.id),
            "agent_id": str(ex.agent_id),
            "status": ex.status,
            "mode": ex.mode,
            "provider": ex.provider,
            "model": ex.model,
            "input_tokens": ex.input_tokens,
            "output_tokens": ex.output_tokens,
            "latency_ms": ex.latency_ms,
            "error": (ex.error or "")[:500] or None,
        }
    }


async def create_execution(
    db: AsyncSession, principal: Principal, ctx: RequestContext, agent_id: uuid.UUID, prompt: str
) -> Execution:
    agent = await agents_service.get_agent(db, principal.organization_id, agent_id)
    if not can_execute(agent.status):
        raise AppError(409, "agent_not_active", f"Agent is '{agent.status}'; only active agents can execute")
    if compute_readiness(agent.execution_mode, agent.provider) == "configured":
        raise AppError(
            409,
            "agent_not_ready",
            f"Agent is set to live but provider '{agent.provider}' has no API key configured. "
            "Set the key on the server or switch the agent to simulated mode.",
        )
    ex = Execution(
        id=uuid.uuid4(),
        organization_id=principal.organization_id,
        agent_id=agent.id,
        requested_by=principal.user_id,
        input_prompt=prompt,
        status="queued",
        mode=agent.execution_mode,
        provider=agent.provider,
        model=agent.model,
        agent_version=agent.version,
        trace_id=ctx.trace_id,
    )
    db.add(ex)
    await db.flush()
    audit.record_for(
        db, principal, ctx, "execution.create", "execution", ex.id,
        after={"agent_id": str(agent.id), "mode": ex.mode, "prompt_chars": len(prompt)},
    )
    return ex


async def run_execution(execution_id: uuid.UUID) -> None:
    """Background task. Prompt and model output are opaque data: they are stored, never interpreted."""
    sm = get_sessionmaker()
    async with sm() as db:
        ex = await db.get(Execution, execution_id)
        if ex is None or ex.status != "queued":
            return
        agent = await db.get(Agent, ex.agent_id)
        if agent is None:
            return
        ex.status = "running"
        ex.started_at = utcnow()
        emit(db, EventType.EXECUTION_STARTED, ex.organization_id, execution_payload(ex), trace_id=ex.trace_id)
        await db.commit()
        request = ModelRequest(
            model=ex.model,
            prompt=ex.input_prompt,
            system=build_system_prompt(agent),
        )
        mode, provider_name, model = ex.mode, ex.provider, ex.model

    text: str | None = None
    error: str | None = None
    input_tokens = output_tokens = latency_ms = None
    try:
        provider = get_provider(provider_name, mode)
        resp = await asyncio.wait_for(provider.complete(request), timeout=settings.execution_timeout_seconds)
        text, input_tokens, output_tokens, latency_ms = (
            resp.text, resp.input_tokens, resp.output_tokens, resp.latency_ms,
        )
    except ProviderError as exc:
        error = exc.message
    except TimeoutError:
        error = "Execution timed out"
    except Exception:  # noqa: BLE001
        logger.exception("execution %s crashed", execution_id)
        error = "Internal error while executing"

    async with sm() as db:
        ex = await db.get(Execution, execution_id)
        if ex is None:
            return
        ex.finished_at = utcnow()
        if error is None:
            ex.status = "succeeded"
            ex.output = text
            ex.input_tokens, ex.output_tokens, ex.latency_ms = input_tokens, output_tokens, latency_ms
            ex.cost_usd = registry.estimate_cost(provider_name, model, input_tokens, output_tokens)
            event = EventType.EXECUTION_COMPLETED
        else:
            ex.status = "failed"
            ex.error = error
            event = EventType.EXECUTION_FAILED
        emit(db, event, ex.organization_id, execution_payload(ex), trace_id=ex.trace_id)
        await db.commit()


async def sweep_interrupted() -> int:
    """At startup: executions left queued/running by a previous process can never finish; fail them."""
    async with get_sessionmaker()() as db:
        rows = (
            await db.execute(select(Execution).where(Execution.status.in_(("queued", "running"))))
        ).scalars().all()
        for ex in rows:
            ex.status = "failed"
            ex.error = "Interrupted by service restart"
            ex.finished_at = utcnow()
            emit(db, EventType.EXECUTION_FAILED, ex.organization_id, execution_payload(ex), trace_id=ex.trace_id)
        await db.commit()
        return len(rows)


async def get_execution(db: AsyncSession, organization_id: uuid.UUID, execution_id: uuid.UUID) -> Execution:
    ex = await db.scalar(
        select(Execution).where(Execution.id == execution_id, Execution.organization_id == organization_id)
    )
    if ex is None:
        raise not_found("Execution")
    return ex


async def list_executions(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    agent_id: uuid.UUID | None,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Execution], int]:
    stmt = select(Execution).where(Execution.organization_id == organization_id)
    if agent_id:
        stmt = stmt.where(Execution.agent_id == agent_id)
    if status:
        stmt = stmt.where(Execution.status == status)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = await db.execute(stmt.order_by(Execution.created_at.desc()).limit(limit).offset(offset))
    return list(rows.scalars().all()), int(total)
