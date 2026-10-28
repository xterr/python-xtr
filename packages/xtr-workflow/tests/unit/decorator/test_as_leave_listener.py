"""A leave listener listens to the leave event of the workflow and place it names."""

from __future__ import annotations

import pytest
from xtr_event_dispatcher.decorator import EventListenerDeclaration, listeners_declared_on

from xtr_workflow.decorator import AsWorkflow, as_leave_listener


@pytest.mark.parametrize(
    ("workflow", "place", "expected"),
    [
        (None, None, "workflow.leave"),
        ("w", None, "workflow.w.leave"),
        ("w", "n", "workflow.w.leave.n"),
    ],
)
def test_the_event_is_narrowed_to_what_is_named(
    workflow: str | None, place: str | None, expected: str
) -> None:
    def listener() -> None: ...

    _ = as_leave_listener(workflow, place)(listener)

    assert listeners_declared_on(listener) == (EventListenerDeclaration(expected),)


def test_a_place_without_a_workflow_uses_the_placeholder() -> None:
    def listener() -> None: ...

    _ = as_leave_listener(place="some")(listener)

    assert listeners_declared_on(listener) == (
        EventListenerDeclaration(f"workflow.{AsWorkflow.NAME_PLACEHOLDER}.leave.some"),
    )
