"""An announce listener listens to the announce event of the workflow and transition it names."""

from __future__ import annotations

import pytest
from xtr_event_dispatcher.decorator import EventListenerDeclaration, listeners_declared_on

from xtr_workflow.decorator import AsWorkflow, as_announce_listener


@pytest.mark.parametrize(
    ("workflow", "transition", "expected"),
    [
        (None, None, "workflow.announce"),
        ("w", None, "workflow.w.announce"),
        ("w", "n", "workflow.w.announce.n"),
    ],
)
def test_the_event_is_narrowed_to_what_is_named(
    workflow: str | None, transition: str | None, expected: str
) -> None:
    def listener() -> None: ...

    _ = as_announce_listener(workflow, transition)(listener)

    assert listeners_declared_on(listener) == (EventListenerDeclaration(expected),)


def test_a_transition_without_a_workflow_uses_the_placeholder() -> None:
    def listener() -> None: ...

    _ = as_announce_listener(transition="some")(listener)

    assert listeners_declared_on(listener) == (
        EventListenerDeclaration(f"workflow.{AsWorkflow.NAME_PLACEHOLDER}.announce.some"),
    )
