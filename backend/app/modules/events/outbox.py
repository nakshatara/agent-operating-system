from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import utcnow
from app.core.logging import trace_id_var
from app.modules.events.envelope import EventType
from app.modules.events.models import OutboxEvent


def emit(
    db: AsyncSession,
    event_type: EventType,
    organization_id: uuid.UUID,
    payload: dict[str, Any],
    *,
    trace_id: str | None = None,
    correlation_id: str | None = None,
) -> OutboxEvent:
    """Stage an event in the outbox. Written in the caller's transaction (transactional outbox);
    it becomes visible to the relay only if the surrounding state change commits."""
    trace = trace_id or trace_id_var.get() or uuid.uuid4().hex
    row = OutboxEvent(
        id=uuid.uuid4(),
        type=event_type.value,
        version=1,
        organization_id=organization_id,
        occurred_at=utcnow(),
        correlation_id=correlation_id or trace,
        trace_id=trace,
        payload=payload,
    )
    db.add(row)
    return row
