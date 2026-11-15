import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.modules.events.envelope import EventEnvelope, EventType


def _env():
    return EventEnvelope(
        event_id=uuid.uuid4(),
        type=EventType.AGENT_CREATED,
        organization_id=uuid.uuid4(),
        occurred_at=datetime.now(UTC),
        correlation_id="c1",
        trace_id="t1",
        payload={"agent": {"id": "x"}},
    )


def test_roundtrip():
    e = _env()
    back = EventEnvelope.from_json(e.to_json().encode())
    assert back == e
    assert back.version == 1


def test_json_shape():
    import json

    data = json.loads(_env().to_json())
    assert set(data) == {
        "event_id", "type", "version", "organization_id", "occurred_at", "correlation_id", "trace_id", "payload",
    }
    assert data["type"] == "AGENT_CREATED"


def test_unknown_type_rejected():
    raw = _env().to_json().replace("AGENT_CREATED", "NOPE")
    with pytest.raises(ValidationError):
        EventEnvelope.from_json(raw)


def test_all_required_event_types_exist():
    names = {t.value for t in EventType}
    assert {"AGENT_CREATED", "EXECUTION_FAILED", "USER_CREATED", "ORGANIZATION_CREATED", "AGENT_RESTARTED"} <= names
    assert len(names) == 14
