"""Agent lifecycle state machine (pure, no I/O)."""

from __future__ import annotations

STATUSES = ("draft", "active", "paused", "disabled", "archived", "terminated")
ACTIONS = ("activate", "pause", "resume", "disable", "restart", "archive", "terminate")

# action -> {from_status: to_status}
TRANSITIONS: dict[str, dict[str, str]] = {
    "activate": {"draft": "active"},
    "pause": {"active": "paused"},
    "resume": {"paused": "active"},
    "disable": {"active": "disabled", "paused": "disabled"},
    "restart": {"active": "active", "disabled": "active"},
    "archive": {"draft": "archived", "paused": "archived", "disabled": "archived"},
    "terminate": {
        "draft": "terminated",
        "active": "terminated",
        "paused": "terminated",
        "disabled": "terminated",
        "archived": "terminated",
    },
}

# Actions that require admin rather than operator privileges (enforced in the router).
ADMIN_ONLY_ACTIONS = frozenset({"archive", "terminate", "disable"})

EDITABLE_STATUSES = frozenset({"draft", "active", "paused", "disabled"})


class InvalidTransition(Exception):
    def __init__(self, status: str, action: str) -> None:
        super().__init__(f"Cannot '{action}' an agent that is '{status}'")
        self.status = status
        self.action = action


def next_status(current: str, action: str) -> str:
    if action not in TRANSITIONS:
        raise ValueError(f"unknown lifecycle action '{action}'")
    try:
        return TRANSITIONS[action][current]
    except KeyError:
        raise InvalidTransition(current, action) from None


def available_actions(status: str) -> list[str]:
    return [a for a in ACTIONS if status in TRANSITIONS[a]]


def can_execute(status: str) -> bool:
    """Only active agents may execute."""
    return status == "active"
