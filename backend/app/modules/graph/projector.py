"""Idempotent projection of domain events into Neo4j (MERGE everywhere; version-guarded for agents)."""

from __future__ import annotations

import logging
from typing import Any

from neo4j.exceptions import ServiceUnavailable, SessionExpired
from neo4j.exceptions import TransientError as Neo4jTransient

from app.modules.events.consumers import EventConsumer, TransientError
from app.modules.events.envelope import AGENT_EVENT_TYPES, EventEnvelope, EventType
from app.modules.graph.client import get_driver

logger = logging.getLogger(__name__)

UPSERT_ORG = """
MERGE (o:Organization {id: $id})
SET o.organization_id = $id, o.name = $name
"""

UPSERT_USER = """
MERGE (o:Organization {id: $org_id})
ON CREATE SET o.organization_id = $org_id
MERGE (u:User {id: $id})
SET u.organization_id = $org_id, u.name = $name, u.role = $role
MERGE (u)-[:USER_BELONGS_TO_ORGANIZATION]->(o)
"""

# Applies only if the incoming version is not older than what the graph holds (out-of-order safety).
UPSERT_AGENT = """
MERGE (o:Organization {id: $org_id})
ON CREATE SET o.organization_id = $org_id
MERGE (a:Agent {id: $id})
WITH a, o
WHERE a.version IS NULL OR a.version <= $version
SET a += $props
MERGE (a)-[:AGENT_BELONGS_TO_ORGANIZATION]->(o)
RETURN a.id AS id
"""

REPLACE_MODEL = """
MATCH (a:Agent {id: $id, organization_id: $org_id})
OPTIONAL MATCH (a)-[old:AGENT_USES_MODEL]->(:Model)
DELETE old
WITH DISTINCT a
MERGE (m:Model {id: $model_id})
SET m.organization_id = $org_id, m.provider = $provider, m.name = $model
MERGE (a)-[:AGENT_USES_MODEL]->(m)
"""

CLEAR_SUPERVISOR = """
MATCH (a:Agent {id: $id, organization_id: $org_id})
OPTIONAL MATCH (a)-[old:AGENT_REPORTS_TO_AGENT]->(:Agent)
DELETE old
"""

SET_SUPERVISOR = """
MATCH (a:Agent {id: $id, organization_id: $org_id})
MERGE (s:Agent {id: $sup_id})
ON CREATE SET s.organization_id = $org_id
MERGE (a)-[:AGENT_REPORTS_TO_AGENT]->(s)
"""


async def upsert_org(tx: Any, org: dict) -> None:
    await tx.run(UPSERT_ORG, {"id": org["id"], "name": org["name"]})


async def upsert_user(tx: Any, user: dict) -> None:
    await tx.run(
        UPSERT_USER,
        {"id": user["id"], "org_id": user["organization_id"], "name": user["full_name"], "role": user["role"]},
    )


async def upsert_agent(tx: Any, agent: dict) -> None:
    org_id = agent["organization_id"]
    props = {
        "organization_id": org_id,
        "name": agent["name"],
        "role": agent["role"],
        "status": agent["status"],
        "autonomy_level": agent["autonomy_level"],
        "provider": agent["provider"],
        "model": agent["model"],
        "execution_mode": agent["execution_mode"],
        "readiness": agent.get("readiness"),
        "version": agent["version"],
    }
    result = await tx.run(
        UPSERT_AGENT, {"id": agent["id"], "org_id": org_id, "version": agent["version"], "props": props}
    )
    applied = await result.single()
    if applied is None:
        return  # stale event; graph already holds a newer version
    params = {"id": agent["id"], "org_id": org_id}
    await tx.run(
        REPLACE_MODEL,
        {**params, "model_id": f"{org_id}:{agent['provider']}:{agent['model']}", "provider": agent["provider"], "model": agent["model"]},
    )
    await tx.run(CLEAR_SUPERVISOR, params)
    if agent.get("supervisor_agent_id"):
        await tx.run(SET_SUPERVISOR, {**params, "sup_id": agent["supervisor_agent_id"]})


def _wrap(exc: Exception) -> TransientError:
    return TransientError(f"neo4j unavailable: {type(exc).__name__}: {exc}")


async def apply_event(envelope: EventEnvelope) -> None:
    payload = envelope.payload
    if envelope.type == EventType.ORGANIZATION_CREATED:
        work = lambda tx: upsert_org(tx, payload["organization"])  # noqa: E731
    elif envelope.type == EventType.USER_CREATED:
        work = lambda tx: upsert_user(tx, payload["user"])  # noqa: E731
    elif envelope.type in AGENT_EVENT_TYPES:
        work = lambda tx: upsert_agent(tx, payload["agent"])  # noqa: E731
    else:
        return  # execution events don't affect the graph in this phase
    try:
        async with get_driver().session() as session:
            await session.execute_write(work)
    except (ServiceUnavailable, SessionExpired, Neo4jTransient, OSError) as exc:
        raise _wrap(exc) from exc


class GraphProjector(EventConsumer):
    name = "agentos-graph-projector"

    async def handle(self, envelope: EventEnvelope) -> None:
        await apply_event(envelope)
