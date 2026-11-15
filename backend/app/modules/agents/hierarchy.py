"""Supervisor hierarchy rules (pure)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping


def would_create_cycle(
    agent_id: uuid.UUID,
    new_supervisor_id: uuid.UUID | None,
    parent_of: Mapping[uuid.UUID, uuid.UUID | None],
) -> bool:
    """True if making `new_supervisor_id` the supervisor of `agent_id` creates a cycle.

    `parent_of` maps agent id -> its current supervisor id. Walks up from the proposed supervisor.
    """
    if new_supervisor_id is None:
        return False
    if new_supervisor_id == agent_id:
        return True
    seen: set[uuid.UUID] = set()
    current: uuid.UUID | None = new_supervisor_id
    while current is not None:
        if current == agent_id or current in seen:
            return True
        seen.add(current)
        current = parent_of.get(current)
    return False
