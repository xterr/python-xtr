"""A guard event collects the reasons listeners give for blocking a transition."""

from __future__ import annotations

from typing import final

import pytest

from tests.support.workflow_stub import WorkflowStub
from xtr_workflow import Marking, Transition, TransitionBlocker
from xtr_workflow.event import Event, GuardEvent

TRANSITION = Transition("publish", "draft", "published")
UNKNOWN_CODE = "e8b5bbb9-5913-4b98-bfa6-65dbd228a82a"


def _event() -> GuardEvent:
    return GuardEvent(object(), Marking({"draft": 1}), TRANSITION, WorkflowStub("post"))


@final
class _Listener:
    def __call__(self, event: GuardEvent) -> None:
        event.set_blocked(True)


@pytest.mark.parametrize(
    ("workflow_name", "node", "expected"),
    [
        (None, None, "workflow.guard"),
        ("post", None, "workflow.post.guard"),
        ("post", "publish", "workflow.post.guard.publish"),
    ],
)
def test_its_names(workflow_name: str | None, node: str | None, expected: str) -> None:
    assert GuardEvent.get_name(workflow_name, node) == expected


def test_it_is_a_workflow_event_keeping_its_transition() -> None:
    event = _event()

    assert isinstance(event, Event)
    assert event.get_transition() is TRANSITION
    assert event.get_workflow_name() == "post"


def test_it_is_not_blocked_until_a_listener_blocks_it() -> None:
    event = _event()

    assert not event.is_blocked()
    assert event.get_transition_blocker_list().is_empty()


def test_a_blocker_added_blocks_it() -> None:
    event = _event()
    blocker = TransitionBlocker("Transition blocker 1", "blocker_1")

    event.add_transition_blocker(blocker)

    assert event.is_blocked()
    assert list(event.get_transition_blocker_list()) == [blocker]


def test_blocking_it_with_a_message_adds_an_unknown_blocker_reading_as_it() -> None:
    event = _event()

    event.set_blocked(True, "You should not pass !!")

    [blocker] = event.get_transition_blocker_list()
    assert blocker.get_message() == "You should not pass !!"
    assert blocker.get_code() == UNKNOWN_CODE


def test_blocking_it_without_a_message_names_the_class_of_the_listener() -> None:
    event = _event()

    _Listener()(event)

    [blocker] = event.get_transition_blocker_list()
    assert blocker.get_message() == (
        "The transition has been blocked by a guard (tests.unit.event.test_guard_event._Listener)."
    )
    assert blocker.get_code() == UNKNOWN_CODE


def test_unblocking_it_forgets_every_blocker() -> None:
    event = _event()
    event.add_transition_blocker(TransitionBlocker("Transition blocker 1", "blocker_1"))
    event.set_blocked(True)

    event.set_blocked(False)

    assert not event.is_blocked()
    assert event.get_transition_blocker_list().is_empty()
