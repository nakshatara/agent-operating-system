from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class EventType(StrEnum):
    AGENT_CREATED = "AGENT_CREATED"
    AGENT_UPDATED = "AGENT_UPDATED"
    AGENT_ACTIVATED = "AGENT_ACTIVATED"
    AGENT_PAUSED = "AGENT_PAUSED"
    AGENT_RESUMED = "AGENT_RESUMED"
    AGENT_DISABLED = "AGENT_DISABLED"
    AGENT_RESTARTED = "AGENT_RESTARTED"
    AGENT_ARCHIVED = "AGENT_ARCHIVED"
    AGENT_TERMINATED = "AGENT_TERMINATED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    USER_CREATED = "USER_CREATED"
    ORGANIZATION_CREATED = "ORGANIZATION_CREATED"


AGENT_EVENT_TYPES = frozenset(t for t in EventType if t.value.startswith("AGENT_"))


class EventEnvelope(BaseModel):
    """Versioned event envelope shared by the outbox, Kafka, and the WebSocket stream."""

    event_id: uuid.UUID
    type: EventType
    version: int = 1
    organization_id: uuid.UUID
    occurred_at: datetime
    correlation_id: str
    trace_id: str
    payload: dict[str, Any]

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str | bytes) -> EventEnvelope:
        return cls.model_validate_json(data)
