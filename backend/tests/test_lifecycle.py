import pytest

from app.modules.agents.lifecycle import (
    ACTIONS,
    STATUSES,
    TRANSITIONS,
    InvalidTransition,
    available_actions,
    can_execute,
    next_status,
)


@pytest.mark.parametrize(
    "start,action,end",
    [
        ("draft", "activate", "active"),
        ("active", "pause", "paused"),
        ("paused", "resume", "active"),
        ("active", "disable", "disabled"),
        ("disabled", "restart", "active"),
        ("disabled", "archive", "archived"),
        ("archived", "terminate", "terminated"),
    ],
)
def test_valid_transitions(start, action, end):
    assert next_status(start, action) == end


@pytest.mark.parametrize(
    "start,action",
    [("draft", "pause"), ("active", "activate"), ("paused", "pause"), ("archived", "resume"), ("active", "archive")],
)
def test_invalid_transitions(start, action):
    with pytest.raises(InvalidTransition):
        next_status(start, action)


def test_terminated_is_final():
    for action in ACTIONS:
        assert "terminated" not in TRANSITIONS[action]
        with pytest.raises(InvalidTransition):
            next_status("terminated", action)
    assert available_actions("terminated") == []


def test_unknown_action():
    with pytest.raises(ValueError):
        next_status("draft", "explode")


def test_only_active_executes():
    assert [s for s in STATUSES if can_execute(s)] == ["active"]


def test_available_actions_draft():
    assert available_actions("draft") == ["activate", "archive", "terminate"]
