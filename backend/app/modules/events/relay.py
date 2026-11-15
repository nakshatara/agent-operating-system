from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.db import get_sessionmaker, utcnow
from app.modules.events.kafka import KafkaPublisher
from app.modules.events.models import OutboxEvent

logger = logging.getLogger(__name__)


async def publish_batch(publisher: KafkaPublisher) -> int:
    """Publish one batch of unpublished outbox rows. Returns number published.

    Rows are locked with FOR UPDATE SKIP LOCKED so multiple relays never double-claim.
    On a publish failure the rows already sent are still marked published (commit), then the
    error is re-raised. Delivery is at-least-once; consumers are idempotent.
    """
    published = 0
    error: Exception | None = None
    async with get_sessionmaker()() as session:
        async with session.begin():
            stmt = (
                select(OutboxEvent)
                .where(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.occurred_at, OutboxEvent.id)
                .limit(settings.relay_batch_size)
                .with_for_update(skip_locked=True)
            )
            rows = (await session.execute(stmt)).scalars().all()
            for row in rows:
                try:
                    envelope = row.to_envelope()
                    await publisher.publish(
                        settings.kafka_events_topic,
                        key=str(row.organization_id).encode(),
                        value=envelope.to_json().encode(),
                    )
                except Exception as exc:  # noqa: BLE001
                    error = exc
                    break
                row.published_at = utcnow()
                published += 1
    if error is not None:
        raise error
    return published


async def run_relay(publisher: KafkaPublisher, stop: asyncio.Event) -> None:
    backoff = 1.0
    logged_down = False
    while not stop.is_set():
        try:
            count = await publish_batch(publisher)
            if logged_down:
                logger.info("outbox relay recovered")
                logged_down = False
            backoff = 1.0
            delay = 0.0 if count >= settings.relay_batch_size else settings.relay_poll_interval_seconds
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            if not logged_down:
                logger.error("outbox relay cannot publish (%s: %s); retrying with backoff", type(exc).__name__, exc)
                logged_down = True
            delay = backoff
            backoff = min(backoff * 2, 30.0)
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except TimeoutError:
            pass
