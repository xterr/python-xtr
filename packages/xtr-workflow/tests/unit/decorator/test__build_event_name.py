"""A listener's event is named as narrowly as its workflow and node say, or left to its class."""

from __future__ import annotations

import pytest

from xtr_workflow.decorator._build_event_name import NAME_PLACEHOLDER, build_event_name


@pytest.mark.parametrize(
    ("workflow", "node", "expected"),
    [
        (None, None, "workflow.guard"),
        ("w", None, "workflow.w.guard"),
        ("w", "n", "workflow.w.guard.n"),
        (None, "n", "workflow.@self.guard.n"),
    ],
)
def test_the_name_is_narrowed_to_what_is_given(
    workflow: str | None, node: str | None, expected: str
) -> None:
    assert build_event_name("guard", workflow, node) == expected


def test_the_placeholder_stands_for_the_workflow_of_the_class() -> None:
    assert NAME_PLACEHOLDER == "@self"
