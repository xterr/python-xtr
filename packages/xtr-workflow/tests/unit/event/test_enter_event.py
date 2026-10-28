"""An enter event is named after the place entered, and carries the transition's context."""

from __future__ import annotations

import pytest

from xtr_workflow import Marking
from xtr_workflow.event import EnterEvent, Event


@pytest.mark.parametrize(
    ("workflow_name", "node", "expected"),
    [
        (None, None, "workflow.enter"),
        ("post", None, "workflow.post.enter"),
        ("post", "published", "workflow.post.enter.published"),
    ],
)
def test_its_names(workflow_name: str | None, node: str | None, expected: str) -> None:
    assert EnterEvent.get_name(workflow_name, node) == expected


def test_it_is_a_workflow_event_whose_context_is_empty_unless_given() -> None:
    event = EnterEvent(object(), Marking())

    assert isinstance(event, Event)
    assert event.get_context() == {}


def test_it_keeps_the_context_it_is_built_with() -> None:
    assert EnterEvent(object(), Marking(), context={"user": "admin"}).get_context() == {
        "user": "admin"
    }
