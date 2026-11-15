"""Versioned Cypher schema migrations. Applied versions are recorded as (:SchemaMigration {version})."""

from __future__ import annotations

import asyncio
import logging

from app.modules.graph.client import get_driver

logger = logging.getLogger(__name__)

_LABELS = ("Organization", "User", "Agent", "Model")

MIGRATIONS: list[tuple[int, list[str]]] = [
    (
        1,
        [
            *(
                f"CREATE CONSTRAINT {label.lower()}_id_unique IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.id IS UNIQUE"
                for label in _LABELS
            ),
            *(
                f"CREATE INDEX {label.lower()}_org_idx IF NOT EXISTS FOR (n:{label}) ON (n.organization_id)"
                for label in _LABELS
            ),
        ],
    ),
]


async def apply_migrations() -> list[int]:
    driver = get_driver()
    applied_now: list[int] = []
    async with driver.session() as session:
        await session.run(
            "CREATE CONSTRAINT schema_migration_version IF NOT EXISTS "
            "FOR (m:SchemaMigration) REQUIRE m.version IS UNIQUE"
        )
        result = await session.run("MATCH (m:SchemaMigration) RETURN m.version AS v")
        done = {r["v"] for r in await result.data()}
        for version, statements in MIGRATIONS:
            if version in done:
                continue
            for statement in statements:
                await session.run(statement)
            await session.run(
                "MERGE (m:SchemaMigration {version: $v}) SET m.applied_at = datetime()", {"v": version}
            )
            applied_now.append(version)
    if applied_now:
        logger.info("neo4j migrations applied: %s", applied_now)
    return applied_now


async def ensure_schema_forever(stop: asyncio.Event) -> None:
    """Retry until Neo4j is reachable so the API can boot without it."""
    delay = 2.0
    while not stop.is_set():
        try:
            await apply_migrations()
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("neo4j schema migration failed (%s: %s); retrying in %.0fs", type(exc).__name__, exc, delay)
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except TimeoutError:
                pass
            delay = min(delay * 2, 30.0)
