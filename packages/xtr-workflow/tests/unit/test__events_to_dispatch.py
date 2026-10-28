"""Which events a workflow dispatches: those listed, or every one but those kept back."""

from __future__ import annotations

import pytest

from xtr_workflow import WorkflowEvents
from xtr_workflow._events_to_dispatch import events_to_dispatch_from
from xtr_workflow.exception import InvalidArgumentError


def test_an_allow_list_lets_out_the_events_listed() -> None:
    allowed = events_to_dispatch_from([WorkflowEvents.ENTER, WorkflowEvents.COMPLETED], "post")

    assert allowed == {WorkflowEvents.ENTER, WorkflowEvents.COMPLETED}


def test_an_empty_list_lets_out_none() -> None:
    assert events_to_dispatch_from([], "post") == frozenset()


def test_a_block_list_lets_out_every_other_event_but_the_guard() -> None:
    allowed = events_to_dispatch_from(
        [f"!{WorkflowEvents.ANNOUNCE}", f"!{WorkflowEvents.LEAVE}", "!workflow.unknown"], "post"
    )

    assert allowed == {
        WorkflowEvents.TRANSITION,
        WorkflowEvents.ENTER,
        WorkflowEvents.ENTERED,
        WorkflowEvents.COMPLETED,
    }


def test_blocking_the_guard_raises() -> None:
    with pytest.raises(InvalidArgumentError, match=r'^The "workflow\.guard" event cannot be'):
        _ = events_to_dispatch_from([f"!{WorkflowEvents.GUARD}"], "post")


def test_mixing_listed_and_blocked_events_raises() -> None:
    with pytest.raises(InvalidArgumentError, match=r"^Cannot mix allow-list and block-list"):
        _ = events_to_dispatch_from([WorkflowEvents.ENTER, f"!{WorkflowEvents.LEAVE}"], "post")
