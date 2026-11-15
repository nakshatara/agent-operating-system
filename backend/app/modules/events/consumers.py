from __future__ import annotations

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.db import get_sessionmaker, utcnow
from app.modules.events.envelope import EventEnvelope
from app.modules.events.kafka import KafkaPublisher
from app.modules.events.models import ProcessedEvent

logger = logging.getLogger(__name__)


class TransientError(Exception):
    """Infrastructure unavailable (Neo4j/Redis down). The event is retried indefinitely, not dead-lettered."""


async def _already_processed(consumer: str, event_id) -> bool:
    async with get_sessionmaker()() as session:
        row = await session.get(ProcessedEvent, (consumer, event_id))
        return row is not None


async def _mark_processed(consumer: str, event_id) -> None:
    async with get_sessionmaker()() as session:
        stmt = (
            pg_insert(ProcessedEvent)
            .values(consumer=consumer, event_id=event_id, processed_at=utcnow())
            .on_conflict_do_nothing()
        )
        await session.execute(stmt)
        await session.commit()


async def _sleep_or_stop(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        pass


class EventConsumer:
    """Base class: one Kafka consumer group per subclass (group id == name)."""

    name: str = "base"

    def __init__(self, publisher: KafkaPublisher) -> None:
        self._publisher = publisher

    async def handle(self, envelope: EventEnvelope) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    async def run(self, stop: asyncio.Event) -> None:
        reported = False
        while not stop.is_set():
            consumer = AIOKafkaConsumer(
                settings.kafka_events_topic,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=self.name,
                enable_auto_commit=False,
                auto_offset_reset="earliest",
            )
            try:
                await consumer.start()
                logger.info("consumer %s started", self.name)
                reported = False
                await self._consume(consumer, stop)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                if not reported:
                    logger.error("consumer %s failed (%s: %s); will retry", self.name, type(exc).__name__, exc)
                    reported = True
            finally:
                try:
                    await consumer.stop()
                except Exception:  # noqa: BLE001
                    pass
            await _sleep_or_stop(stop, 5.0)

    async def _consume(self, consumer: AIOKafkaConsumer, stop: asyncio.Event) -> None:
        while not stop.is_set():
            batches = await consumer.getmany(timeout_ms=1000, max_records=50)
            for tp, messages in batches.items():
                for msg in messages:
                    await self._process(msg.value, stop)
                    await consumer.commit({tp: msg.offset + 1})

    async def _process(self, raw: bytes, stop: asyncio.Event) -> None:
        try:
            envelope = EventEnvelope.from_json(raw)
        except Exception as exc:  # noqa: BLE001
            await self._dead_letter(raw, f"unparseable envelope: {exc}")
            return

        if await _already_processed(self.name, envelope.event_id):
            return

        attempts = 0
        delay = 1.0
        while True:
            try:
                await self.handle(envelope)
                break
            except TransientError as exc:
                if stop.is_set():
                    raise
                logger.warning("consumer %s: transient failure (%s); retrying in %.0fs", self.name, exc, delay)
                await _sleep_or_stop(stop, delay)
                delay = min(delay * 2, 30.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                attempts += 1
                logger.warning("consumer %s: attempt %d failed for %s: %s", self.name, attempts, envelope.event_id, exc)
                if attempts >= settings.consumer_max_retries:
                    await self._dead_letter(raw, f"{type(exc).__name__}: {exc}", envelope)
                    return
                await _sleep_or_stop(stop, delay)
                delay = min(delay * 2, 30.0)
        await _mark_processed(self.name, envelope.event_id)

    async def _dead_letter(
        self, raw: bytes, error: str, envelope: EventEnvelope | None = None
    ) -> None:
        record = {
            "consumer": self.name,
            "error": error[:1000],
            "failed_at": utcnow().isoformat(),
            "original": raw.decode("utf-8", errors="replace"),
        }
        key = str(envelope.organization_id).encode() if envelope else b"unparseable"
        logger.error("consumer %s dead-lettering event: %s", self.name, error[:200])
        # If this publish fails the exception propagates and the offset is not committed (redelivery).
        await self._publisher.publish(settings.kafka_dlq_topic, key=key, value=json.dumps(record).encode())
