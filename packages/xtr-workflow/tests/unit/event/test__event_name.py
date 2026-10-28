"""An event name narrows from every workflow, to one workflow, to one place or transition."""

from __future__ import annotations

import pytest

from xtr_workflow.event import EnterEvent, GuardEvent
from xtr_workflow.event._event_name import event_name
from xtr_workflow.exception import InvalidArgumentError


@pytest.mark.parametrize(
    ("workflow_name", "node", "expected"),
    [
        pytest.param(None, None, "workflow.guard", id="every-workflow"),
        pytest.param("post", None, "workflow.post.guard", id="one-workflow"),
        pytest.param("post", "publish", "workflow.post.guard.publish", id="one-node"),
    ],
)
def test_it_is_built_from_the_short_name_of_the_event_class(
    workflow_name: str | None, node: str | None, expected: str
) -> None:
    assert event_name(GuardEvent, workflow_name, node) == expected


def test_a_node_without_a_workflow_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = EnterEvent.get_name(None, "place")

    assert str(raised.value) == "Missing workflow name."
