from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_sessionmaker
from app.core.redis import get_redis
from app.modules.agents.models import Agent
from app.modules.agents.readiness import compute_readiness
from app.modules.events.kafka import kafka_publisher
from app.modules.graph.client import get_driver
from app.modules.runtime.models import Execution


async def _probe(check: Callable[[], Awaitable[None]]) -> dict[str, Any]:
    try:
        await asyncio.wait_for(check(), timeout=2.0)
        return {"ok": True, "detail": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": type(exc).__name__}


async def _pg() -> None:
    async with get_sessionmaker()() as s:
        await s.execute(text("SELECT 1"))


async def _redis() -> None:
    await get_redis().ping()


async def _neo4j() -> None:
    await get_driver().verify_connectivity()


async def _kafka() -> None:
    if not kafka_publisher.connected:
        raise ConnectionError("producer not connected")


async def health() -> dict[str, dict[str, Any]]:
    pg, neo, kafka, redis = await asyncio.gather(
        _probe(_pg), _probe(_neo4j), _probe(_kafka), _probe(_redis)
    )
    return {"postgres": pg, "neo4j": neo, "kafka": kafka, "redis": redis}


async def summary(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    agent_rows = (
        await db.execute(
            select(Agent.status, Agent.execution_mode, Agent.provider, func.count())
            .where(Agent.organization_id == organization_id)
            .group_by(Agent.status, Agent.execution_mode, Agent.provider)
        )
    ).all()
    by_status: dict[str, int] = {}
    by_readiness = {"simulated": 0, "configured": 0, "live": 0}
    total = 0
    for status, mode, provider, count in agent_rows:
        total += count
        by_status[status] = by_status.get(status, 0) + count
        by_readiness[compute_readiness(mode, provider)] += count

    exec_rows = (
        await db.execute(
            select(Execution.status, func.count())
            .where(Execution.organization_id == organization_id)
            .group_by(Execution.status)
        )
    ).all()
    ex = {s: 0 for s in ("queued", "running", "succeeded", "failed")}
    for status, count in exec_rows:
        ex[status] = count

    tok = (
        await db.execute(
            select(
                func.coalesce(func.sum(Execution.input_tokens), 0),
                func.coalesce(func.sum(Execution.output_tokens), 0),
            ).where(Execution.organization_id == organization_id)
        )
    ).one()
    tin, tout = int(tok[0]), int(tok[1])
    return {
        "agents": {
            "total": total,
            "active": by_status.get("active", 0),
            "paused": by_status.get("paused", 0),
            "by_status": by_status,
            "by_readiness": by_readiness,
        },
        "executions": {**ex, "total": sum(ex.values())},
        "tokens": {"input": tin, "output": tout, "total": tin + tout},
        "health": await health(),
    }
