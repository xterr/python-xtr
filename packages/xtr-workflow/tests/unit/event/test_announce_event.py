"""An announce event is named after the transition now enabled, and carries the context."""

from __future__ import annotations

import pytest

from xtr_workflow import Marking
from xtr_workflow.event import AnnounceEvent, Event


@pytest.mark.parametrize(
    ("workflow_name", "node", "expected"),
    [
        (None, None, "workflow.announce"),
        ("post", None, "workflow.post.announce"),
        ("post", "publish", "workflow.post.announce.publish"),
    ],
)
def test_its_names(workflow_name: str | None, node: str | None, expected: str) -> None:
    assert AnnounceEvent.get_name(workflow_name, node) == expected


def test_it_is_a_workflow_event_whose_context_is_empty_unless_given() -> None:
    event = AnnounceEvent(object(), Marking())

    assert isinstance(event, Event)
    assert event.get_context() == {}


def test_it_keeps_the_context_it_is_built_with() -> None:
    assert AnnounceEvent(object(), Marking(), context={"user": "admin"}).get_context() == {
        "user": "admin"
    }
