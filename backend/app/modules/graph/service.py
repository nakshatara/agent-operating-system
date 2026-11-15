from __future__ import annotations

import uuid
from typing import Any

from neo4j.exceptions import Neo4jError, ServiceUnavailable
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, not_found
from app.modules.agents.models import Agent
from app.modules.agents.service import agent_snapshot
from app.modules.graph import projector
from app.modules.graph.client import get_driver
from app.modules.identity.models import User
from app.modules.identity.service import organization_snapshot, user_snapshot
from app.modules.organizations.models import Organization

NODES_QUERY = """
MATCH (n)
WHERE n.organization_id = $org_id AND (n:Organization OR n:User OR n:Agent OR n:Model)
RETURN n.id AS id, labels(n)[0] AS type, properties(n) AS props
"""

EDGES_QUERY = """
MATCH (a)-[r]->(b)
WHERE a.organization_id = $org_id AND b.organization_id = $org_id
  AND type(r) IN ['USER_BELONGS_TO_ORGANIZATION', 'AGENT_BELONGS_TO_ORGANIZATION',
                  'AGENT_REPORTS_TO_AGENT', 'AGENT_USES_MODEL']
RETURN a.id AS source, b.id AS target, type(r) AS type
"""

HIERARCHY_QUERY = """
MATCH (root:Agent {id: $id, organization_id: $org_id})
MATCH path = (d:Agent)-[:AGENT_REPORTS_TO_AGENT*0..10]->(root)
WHERE d.organization_id = $org_id
RETURN d.id AS id, d.name AS name, d.role AS role, d.status AS status,
       length(path) AS depth,
       CASE WHEN length(path) = 0 THEN null ELSE nodes(path)[1].id END AS parent_id
ORDER BY depth, name
"""

DELETE_TENANT = """
MATCH (n)
WHERE n.organization_id = $org_id AND (n:Organization OR n:User OR n:Agent OR n:Model)
DETACH DELETE n
"""


def _label(node_type: str, props: dict[str, Any]) -> str:
    return str(props.get("name") or props.get("full_name") or props.get("id", ""))


async def _read(query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        async with get_driver().session() as session:
            result = await session.run(query, params)
            return await result.data()
    except (ServiceUnavailable, Neo4jError, OSError) as exc:
        raise AppError(503, "graph_unavailable", f"Graph store unavailable: {type(exc).__name__}") from exc


async def get_graph(org_id: uuid.UUID) -> dict[str, Any]:
    params = {"org_id": str(org_id)}
    nodes = await _read(NODES_QUERY, params)
    edges = await _read(EDGES_QUERY, params)
    return {
        "nodes": [
            {"id": n["id"], "type": n["type"], "label": _label(n["type"], n["props"]), "properties": n["props"]}
            for n in nodes
        ],
        "edges": [{"source": e["source"], "target": e["target"], "type": e["type"]} for e in edges],
    }


async def get_hierarchy(org_id: uuid.UUID, agent_id: uuid.UUID) -> dict[str, Any]:
    rows = await _read(HIERARCHY_QUERY, {"id": str(agent_id), "org_id": str(org_id)})
    if not rows:
        raise not_found("Agent in graph")
    by_id: dict[str, dict[str, Any]] = {
        r["id"]: {
            "id": r["id"], "name": r["name"], "role": r["role"], "status": r["status"],
            "depth": r["depth"], "parent_id": r["parent_id"], "children": [],
        }
        for r in rows
    }
    root = by_id[str(agent_id)]
    for node in by_id.values():
        parent = by_id.get(node["parent_id"]) if node["parent_id"] else None
        if parent is not None:
            parent["children"].append(node)
    return {"root_id": str(agent_id), "count": len(by_id), "tree": root}


async def reconcile(db: AsyncSession, org_id: uuid.UUID) -> dict[str, int]:
    """Rebuild the tenant's graph from PostgreSQL (the source of truth)."""
    org = await db.get(Organization, org_id)
    if org is None:
        raise not_found("Organization")
    users = (await db.execute(select(User).where(User.organization_id == org_id))).scalars().all()
    agents = (await db.execute(select(Agent).where(Agent.organization_id == org_id))).scalars().all()
    try:
        async with get_driver().session() as session:

            async def work(tx: Any) -> None:
                await tx.run(DELETE_TENANT, {"org_id": str(org_id)})
                await projector.upsert_org(tx, organization_snapshot(org))
                for u in users:
                    await projector.upsert_user(tx, user_snapshot(u))
                for a in agents:
                    await projector.upsert_agent(tx, agent_snapshot(a))

            await session.execute_write(work)
    except (ServiceUnavailable, Neo4jError, OSError) as exc:
        raise AppError(503, "graph_unavailable", f"Graph store unavailable: {type(exc).__name__}") from exc
    return {"organizations": 1, "users": len(users), "agents": len(agents)}
