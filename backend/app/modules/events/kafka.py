from __future__ import annotations

import asyncio
import logging

from aiokafka import AIOKafkaProducer

from app.core.config import settings

logger = logging.getLogger(__name__)


class KafkaPublisher:
    """Lazily-started producer. start failures are reported to the caller, which retries later."""

    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._producer is not None

    async def ensure_started(self) -> None:
        if self._producer is not None:
            return
        async with self._lock:
            if self._producer is not None:
                return
            producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                acks="all",
                request_timeout_ms=10000,
            )
            try:
                await producer.start()
            except Exception:
                try:
                    await producer.stop()
                except Exception:  # noqa: BLE001
                    pass
                raise
            self._producer = producer
            logger.info("kafka producer connected to %s", settings.kafka_bootstrap_servers)

    async def publish(self, topic: str, key: bytes, value: bytes) -> None:
        await self.ensure_started()
        assert self._producer is not None
        try:
            await self._producer.send_and_wait(topic, value=value, key=key)
        except Exception:
            # Drop the producer so the next attempt reconnects from scratch.
            await self.stop()
            raise

    async def stop(self) -> None:
        producer, self._producer = self._producer, None
        if producer is not None:
            try:
                await producer.stop()
            except Exception:  # noqa: BLE001
                logger.debug("error stopping kafka producer", exc_info=True)


kafka_publisher = KafkaPublisher()
