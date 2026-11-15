from __future__ import annotations

from redis.exceptions import RedisError

from app.core.redis import get_redis
from app.modules.events.consumers import EventConsumer, TransientError
from app.modules.events.envelope import EventEnvelope


def channel_for(organization_id) -> str:
    return f"events:{organization_id}"


class LiveFanoutConsumer(EventConsumer):
    """Publishes every event to a per-tenant Redis channel consumed by WebSocket clients."""

    name = "agentos-live-fanout"

    async def handle(self, envelope: EventEnvelope) -> None:
        try:
            await get_redis().publish(channel_for(envelope.organization_id), envelope.to_json())
        except (RedisError, OSError) as exc:
            raise TransientError(f"redis unavailable: {exc}") from exc
