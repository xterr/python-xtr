"""A completed event is named after the transition, and carries its context."""

from __future__ import annotations

import pytest

from xtr_workflow import Marking
from xtr_workflow.event import CompletedEvent, Event


@pytest.mark.parametrize(
    ("workflow_name", "node", "expected"),
    [
        (None, None, "workflow.completed"),
        ("post", None, "workflow.post.completed"),
        ("post", "publish", "workflow.post.completed.publish"),
    ],
)
def test_its_names(workflow_name: str | None, node: str | None, expected: str) -> None:
    assert CompletedEvent.get_name(workflow_name, node) == expected


def test_it_is_a_workflow_event_whose_context_is_empty_unless_given() -> None:
    event = CompletedEvent(object(), Marking())

    assert isinstance(event, Event)
    assert event.get_context() == {}


def test_it_keeps_the_context_it_is_built_with() -> None:
    assert CompletedEvent(object(), Marking(), context={"user": "admin"}).get_context() == {
        "user": "admin"
    }
