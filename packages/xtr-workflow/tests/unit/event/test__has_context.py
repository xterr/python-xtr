"""An event with a context hands out a copy of it."""

from __future__ import annotations

from xtr_workflow import Marking
from xtr_workflow.event import LeaveEvent
from xtr_workflow.event._has_context import HasContextTrait


def test_an_event_with_a_context_has_the_trait() -> None:
    assert isinstance(LeaveEvent(object(), Marking()), HasContextTrait)


def test_changing_the_context_it_returns_leaves_it_unchanged() -> None:
    event = LeaveEvent(object(), Marking(), context={"user": "admin"})

    event.get_context()["user"] = "guest"

    assert event.get_context() == {"user": "admin"}


def test_changing_the_context_it_was_built_with_leaves_it_unchanged() -> None:
    context: dict[str, object] = {"user": "admin"}
    event = LeaveEvent(object(), Marking(), context=context)

    context["user"] = "guest"

    assert event.get_context() == {"user": "admin"}
