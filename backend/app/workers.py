"""Background workers: outbox relay, Kafka consumers, graph schema migration. All tolerate dead infra."""

from __future__ import annotations

import asyncio
import logging

from app.modules.events.fanout import LiveFanoutConsumer
from app.modules.events.kafka import kafka_publisher
from app.modules.events.relay import run_relay
from app.modules.graph.migrations import ensure_schema_forever
from app.modules.graph.projector import GraphProjector
from app.modules.runtime.service import sweep_interrupted

logger = logging.getLogger(__name__)


class WorkerSet:
    def __init__(self) -> None:
        self.stop = asyncio.Event()
        self.tasks: list[asyncio.Task] = []

    def start(self) -> None:
        async def sweep() -> None:
            try:
                n = await sweep_interrupted()
                if n:
                    logger.warning("marked %d interrupted executions as failed", n)
            except Exception as exc:  # noqa: BLE001
                logger.error("startup sweep failed: %s", exc)

        coros = {
            "sweep": sweep(),
            "outbox-relay": run_relay(kafka_publisher, self.stop),
            "graph-schema": ensure_schema_forever(self.stop),
            "graph-projector": GraphProjector(kafka_publisher).run(self.stop),
            "live-fanout": LiveFanoutConsumer(kafka_publisher).run(self.stop),
        }
        self.tasks = [asyncio.create_task(c, name=n) for n, c in coros.items()]

    async def shutdown(self) -> None:
        self.stop.set()
        for t in self.tasks:
            t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await kafka_publisher.stop()
