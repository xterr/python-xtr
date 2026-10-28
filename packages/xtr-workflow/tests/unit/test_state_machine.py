"""A state machine is a workflow whose subject is in one place, kept by its name.

Every test runs once with a subject whose accessors are plain methods and
once with one whose accessors are coroutines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_event_dispatcher import EventDispatcher

from tests.support.definitions import create_complex_state_machine_definition
from tests.support.subjects import SUBJECT_TYPES, AnySubject, keep, kept_by
from xtr_workflow import StateMachine, TransitionBlocker, Workflow
from xtr_workflow.exception import NotEnabledTransitionError
from xtr_workflow.marking_store import MethodMarkingStore

if TYPE_CHECKING:
    from xtr_workflow.event import GuardEvent

pytestmark = pytest.mark.anyio


@pytest.fixture(params=SUBJECT_TYPES, ids=["sync", "async"])
def subject(request: pytest.FixtureRequest) -> AnySubject:
    return cast("type[AnySubject]", request.param)()


def _block_naming_the_place_left(event: GuardEvent) -> None:
    place = event.get_transition().get_froms(as_arc=True)[0].place
    event.add_transition_blocker(
        TransitionBlocker(f"Transition blocker of place {place}", "blocker")
    )


def _guarded_state_machine() -> StateMachine:
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.guard", _block_naming_the_place_left)
    return StateMachine(create_complex_state_machine_definition(), None, dispatcher)


def test_it_is_a_workflow() -> None:
    assert isinstance(StateMachine(create_complex_state_machine_definition()), Workflow)


async def test_it_keeps_the_name_of_the_one_place_unless_given_a_store(
    subject: AnySubject,
) -> None:
    state_machine = StateMachine(create_complex_state_machine_definition())

    _ = await state_machine.apply(subject, "t1")

    assert isinstance(state_machine.get_marking_store(), MethodMarkingStore)
    assert await kept_by(subject) == "b"


async def test_it_uses_the_store_it_is_given(subject: AnySubject) -> None:
    marking_store = MethodMarkingStore()
    state_machine = StateMachine(create_complex_state_machine_definition(), marking_store)

    _ = await state_machine.apply(subject, "t1")

    assert state_machine.get_marking_store() is marking_store
    assert await kept_by(subject) == {"b": 1}


@pytest.mark.parametrize(
    ("place", "expected"),
    [
        # In "a" or in "d", one of the two transitions named t1 leaves it.
        ("a", True),
        ("d", True),
        ("b", False),
    ],
)
async def test_can_is_true_in_a_place_a_transition_of_the_name_leaves(
    subject: AnySubject, place: str, expected: bool
) -> None:
    await keep(subject, place)
    state_machine = StateMachine(create_complex_state_machine_definition())

    assert await state_machine.can(subject, "t1") is expected


@pytest.mark.parametrize("transition_name", ["t2", "t3"])
async def test_can_is_true_for_every_transition_leaving_the_place(
    subject: AnySubject, transition_name: str
) -> None:
    await keep(subject, "b")
    state_machine = StateMachine(create_complex_state_machine_definition())

    assert await state_machine.can(subject, transition_name)


@pytest.mark.parametrize(("place", "blocked"), [("a", False), ("d", False), ("b", True)])
async def test_build_transition_blocker_list_is_empty_in_a_place_a_transition_leaves(
    subject: AnySubject, place: str, blocked: bool
) -> None:
    await keep(subject, place)
    state_machine = StateMachine(create_complex_state_machine_definition())

    blockers = await state_machine.build_transition_blocker_list(subject, "t1")

    assert blockers.is_empty() is not blocked


@pytest.mark.parametrize("transition_name", ["t2", "t3"])
async def test_build_transition_blocker_list_is_empty_for_every_transition_leaving_the_place(
    subject: AnySubject, transition_name: str
) -> None:
    await keep(subject, "b")
    state_machine = StateMachine(create_complex_state_machine_definition())

    blockers = await state_machine.build_transition_blocker_list(subject, transition_name)

    assert blockers.is_empty()


@pytest.mark.parametrize("place", ["a", "d"])
async def test_build_transition_blocker_list_prefers_the_guard_over_the_marking(
    subject: AnySubject, place: str
) -> None:
    # Of the transitions sharing a name, the one the marking enables tells why it is blocked.
    await keep(subject, place)
    state_machine = _guarded_state_machine()

    [blocker] = await state_machine.build_transition_blocker_list(subject, "t1")

    assert blocker.get_message() == f"Transition blocker of place {place}"
    assert blocker.get_code() == "blocker"


async def test_apply_raises_with_the_blockers_of_the_guard_over_the_marking(
    subject: AnySubject,
) -> None:
    # Every transition sharing the name is weighed, not only the first.
    state_machine = _guarded_state_machine()

    with pytest.raises(NotEnabledTransitionError) as caught:
        _ = await state_machine.apply(subject, "t1")

    [blocker] = caught.value.get_transition_blocker_list()
    assert blocker.get_message() == "Transition blocker of place a"
    assert blocker.get_code() == "blocker"
