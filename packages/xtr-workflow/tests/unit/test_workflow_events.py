"""Every workflow event has one name, and its class maps to it."""

from __future__ import annotations

import pytest

from xtr_workflow import WorkflowEvents
from xtr_workflow.event import (
    AnnounceEvent,
    CompletedEvent,
    EnteredEvent,
    EnterEvent,
    GuardEvent,
    LeaveEvent,
    TransitionEvent,
)


def test_its_names_are_the_ones_every_listener_knows() -> None:
    assert WorkflowEvents.GUARD == "workflow.guard"
    assert WorkflowEvents.LEAVE == "workflow.leave"
    assert WorkflowEvents.TRANSITION == "workflow.transition"
    assert WorkflowEvents.ENTER == "workflow.enter"
    assert WorkflowEvents.ENTERED == "workflow.entered"
    assert WorkflowEvents.COMPLETED == "workflow.completed"
    assert WorkflowEvents.ANNOUNCE == "workflow.announce"


def test_its_aliases_map_each_event_class_to_its_name() -> None:
    assert dict(WorkflowEvents.ALIASES) == {
        GuardEvent: "workflow.guard",
        LeaveEvent: "workflow.leave",
        TransitionEvent: "workflow.transition",
        EnterEvent: "workflow.enter",
        EnteredEvent: "workflow.entered",
        CompletedEvent: "workflow.completed",
        AnnounceEvent: "workflow.announce",
    }


def test_each_alias_is_the_name_its_event_class_builds() -> None:
    assert [
        GuardEvent.get_name(),
        LeaveEvent.get_name(),
        TransitionEvent.get_name(),
        EnterEvent.get_name(),
        EnteredEvent.get_name(),
        CompletedEvent.get_name(),
        AnnounceEvent.get_name(),
    ] == list(WorkflowEvents.ALIASES.values())


def test_its_aliases_cannot_be_changed() -> None:
    with pytest.raises(TypeError):
        WorkflowEvents.ALIASES[GuardEvent] = "workflow.other"  # ty: ignore[invalid-assignment] # pyright: ignore[reportIndexIssue] — writing to it is what the test checks is refused
