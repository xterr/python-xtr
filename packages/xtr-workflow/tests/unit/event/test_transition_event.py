"""A transition event carries the context the transition runs with, which a listener may replace."""

from __future__ import annotations

import pytest

from xtr_workflow import Marking
from xtr_workflow.event import Event, TransitionEvent


@pytest.mark.parametrize(
    ("workflow_name", "node", "expected"),
    [
        (None, None, "workflow.transition"),
        ("post", None, "workflow.post.transition"),
        ("post", "publish", "workflow.post.transition.publish"),
    ],
)
def test_its_names(workflow_name: str | None, node: str | None, expected: str) -> None:
    assert TransitionEvent.get_name(workflow_name, node) == expected


def test_it_is_a_workflow_event_whose_context_is_empty_unless_given() -> None:
    event = TransitionEvent(object(), Marking())

    assert isinstance(event, Event)
    assert event.get_context() == {}


def test_it_keeps_the_context_it_is_built_with() -> None:
    assert TransitionEvent(object(), Marking(), context={"user": "admin"}).get_context() == {
        "user": "admin"
    }


def test_a_listener_can_replace_its_context() -> None:
    event = TransitionEvent(object(), Marking(), context={"user": "admin"})

    event.set_context({"user": "guest"})

    assert event.get_context() == {"user": "guest"}
