"""A workflow moves a subject through its definition, asking and telling listeners at each step.

Every test that reads or writes a subject runs once with plain accessors and
once with coroutines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_event_dispatcher import EventDispatcher

from tests.support.definitions import (
    create_complex_workflow_definition,
    create_simple_workflow_definition,
    create_workflow_with_same_name_back_transition,
    create_workflow_with_same_name_transition,
)
from tests.support.event_dispatcher_spy import EventDispatcherSpy
from tests.support.subjects import SUBJECT_TYPES, AnySubject, keep, kept_by
from xtr_workflow import (
    Arc,
    Definition,
    Marking,
    Transition,
    TransitionBlocker,
    Workflow,
    WorkflowEvents,
    WorkflowInterface,
)
from xtr_workflow.event import (
    AnnounceEvent,
    EnteredEvent,
    EnterEvent,
    Event,
    GuardEvent,
    LeaveEvent,
    TransitionEvent,
)
from xtr_workflow.exception import (
    InvalidArgumentError,
    LogicError,
    NotEnabledTransitionError,
    UndefinedTransitionError,
)
from xtr_workflow.marking_store import MethodMarkingStore

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio

NAME = "workflow_name"
MARKING_CODE = "19beefc8-6b1e-4716-9d07-a39bd6d16e34"
UNKNOWN_CODE = "e8b5bbb9-5913-4b98-bfa6-65dbd228a82a"

_ContextEvent = LeaveEvent | TransitionEvent | EnterEvent | EnteredEvent | AnnounceEvent


@pytest.fixture(params=SUBJECT_TYPES, ids=["sync", "async"])
def subject(request: pytest.FixtureRequest) -> AnySubject:
    return cast("type[AnySubject]", request.param)()


@final
class _Guard:
    """Blocks without a message, so the blocker names this class."""

    def block(self, event: GuardEvent) -> None:
        event.set_blocked(True)


def _block(event: GuardEvent) -> None:
    event.set_blocked(True)


def _sorted_places(marking: Marking) -> list[tuple[str, int]]:
    return sorted(marking.get_places().items())


async def _kept_places(subject: AnySubject) -> list[tuple[str, int]]:
    """Return the places ``subject`` keeps, in the order the store wrote them."""
    return list(cast("dict[str, int]", await kept_by(subject)).items())


def _two_transitions_from_a() -> Definition:
    return Definition(["a", "b", "c"], [Transition("a-b", "a", "b"), Transition("a-c", "a", "c")])


# The workflow itself.


def test_it_is_a_workflow() -> None:
    assert isinstance(Workflow(Definition([], [])), WorkflowInterface)


def test_it_answers_with_what_it_was_built_with() -> None:
    definition = create_simple_workflow_definition()
    marking_store = MethodMarkingStore()

    workflow = Workflow(definition, marking_store, None, NAME)

    assert workflow.get_name() == NAME
    assert workflow.get_definition() is definition
    assert workflow.get_marking_store() is marking_store
    assert workflow.get_metadata_store() is definition.get_metadata_store()


async def test_it_is_unnamed_and_keeps_a_dict_of_places_unless_told_otherwise(
    subject: AnySubject,
) -> None:
    workflow = Workflow(create_complex_workflow_definition())

    _ = await workflow.apply(subject, "t1")

    assert workflow.get_name() == "unnamed"
    assert isinstance(workflow.get_marking_store(), MethodMarkingStore)
    assert await kept_by(subject) == {"b": 1, "c": 1}


def test_its_context_keys_and_default_initial_context() -> None:
    assert Workflow.DISABLE_LEAVE_EVENT == "workflow_disable_leave_event"
    assert Workflow.DISABLE_TRANSITION_EVENT == "workflow_disable_transition_event"
    assert Workflow.DISABLE_ENTER_EVENT == "workflow_disable_enter_event"
    assert Workflow.DISABLE_ENTERED_EVENT == "workflow_disable_entered_event"
    assert Workflow.DISABLE_COMPLETED_EVENT == "workflow_disable_completed_event"
    assert Workflow.DISABLE_ANNOUNCE_EVENT == "workflow_disable_announce_event"
    assert Workflow.DEFAULT_INITIAL_CONTEXT == {"initial": True}


def test_its_default_initial_context_cannot_be_changed() -> None:
    with pytest.raises(TypeError):
        cast("dict[str, object]", Workflow.DEFAULT_INITIAL_CONTEXT)["initial"] = False


# Reading the marking.


async def test_get_marking_without_an_initial_place_raises(subject: AnySubject) -> None:
    workflow = Workflow(Definition([], []), MethodMarkingStore())

    with pytest.raises(LogicError) as caught:
        _ = await workflow.get_marking(subject)

    assert str(caught.value) == (
        'The Marking is empty and there is no initial place for workflow "unnamed".'
    )


async def test_get_marking_in_a_place_of_a_workflow_without_places_raises(
    subject: AnySubject,
) -> None:
    await keep(subject, {"nope": 1})
    workflow = Workflow(Definition([], []), MethodMarkingStore())

    with pytest.raises(LogicError) as caught:
        _ = await workflow.get_marking(subject)

    assert str(caught.value) == (
        'Place "nope" is not valid for workflow "unnamed". '
        "It seems you forgot to add places to the current workflow."
    )


async def test_get_marking_in_a_place_the_definition_lacks_raises(subject: AnySubject) -> None:
    await keep(subject, {"nope": 1})
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())

    with pytest.raises(LogicError) as caught:
        _ = await workflow.get_marking(subject)

    assert str(caught.value) == 'Place "nope" is not valid for workflow "unnamed".'


async def test_get_marking_of_a_subject_in_no_place_marks_the_initial_place(
    subject: AnySubject,
) -> None:
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())

    marking = await workflow.get_marking(subject)

    assert marking.has("a")
    assert await kept_by(subject) == {"a": 1}


async def test_get_marking_stores_the_initial_marking_without_a_context(
    subject: AnySubject,
) -> None:
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())

    _ = await workflow.get_marking(subject, {"lorem": "ipsum"})

    assert subject.get_context() == {}


async def test_get_marking_returns_the_marking_the_subject_keeps(subject: AnySubject) -> None:
    await keep(subject, {"b": 1, "c": 1})
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())

    marking = await workflow.get_marking(subject)

    assert marking.has("b")
    assert marking.has("c")


# Telling whether a transition can be applied.


async def test_can_is_false_for_an_undefined_transition(subject: AnySubject) -> None:
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())

    assert not await workflow.can(subject, "foobar")


@pytest.mark.parametrize(
    ("marking", "transition_name", "expected"),
    [
        (None, "t1", True),
        (None, "t2", False),
        ({"b": 1}, "t1", False),
        # Every place a workflow transition leaves must hold a token.
        ({"b": 1}, "t2", False),
        ({"b": 1, "c": 1}, "t1", False),
        ({"b": 1, "c": 1}, "t2", True),
        ({"f": 1}, "t5", False),
        ({"f": 1}, "t6", True),
    ],
)
async def test_can_needs_a_token_in_every_place_the_transition_leaves(
    subject: AnySubject,
    marking: Mapping[str, int] | None,
    transition_name: str,
    expected: bool,
) -> None:
    await keep(subject, marking)
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())

    assert await workflow.can(subject, transition_name) is expected


async def test_can_is_false_when_a_guard_blocks(subject: AnySubject) -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_listener(f"workflow.{NAME}.guard.t1", _block)
    workflow = Workflow(
        create_complex_workflow_definition(), MethodMarkingStore(), dispatcher, NAME
    )

    assert not await workflow.can(subject, "t1")


async def test_can_guards_only_the_transitions_of_the_name_asked(subject: AnySubject) -> None:
    dispatcher = EventDispatcher()
    workflow = Workflow(
        create_complex_workflow_definition(), MethodMarkingStore(), dispatcher, NAME
    )
    _ = await workflow.apply(subject, "t1")
    _ = await workflow.apply(subject, "t2")
    guarded: list[str] = []
    dispatcher.add_listener(f"workflow.{NAME}.guard.t3", lambda: guarded.append(f"{NAME}.guard.t3"))
    dispatcher.add_listener(f"workflow.{NAME}.guard.t4", lambda: guarded.append(f"{NAME}.guard.t4"))

    _ = await workflow.can(subject, "t3")

    assert guarded == [f"{NAME}.guard.t3"]


@pytest.mark.parametrize(
    ("marking", "transition_name", "expected"),
    [
        (None, "a_to_bc", True),
        (None, "b_to_c", False),
        (None, "to_a", False),
        ({"b": 1}, "a_to_bc", False),
        ({"b": 1}, "b_to_c", True),
        ({"b": 1}, "to_a", True),
    ],
)
async def test_can_is_true_when_any_transition_of_the_name_is_enabled(
    subject: AnySubject,
    marking: Mapping[str, int] | None,
    transition_name: str,
    expected: bool,
) -> None:
    await keep(subject, marking)
    workflow = Workflow(create_workflow_with_same_name_transition(), MethodMarkingStore())

    assert await workflow.can(subject, transition_name) is expected


# Telling why a transition is blocked.


async def test_build_transition_blocker_list_of_an_undefined_transition_raises(
    subject: AnySubject,
) -> None:
    workflow = Workflow(create_simple_workflow_definition(), MethodMarkingStore())

    with pytest.raises(UndefinedTransitionError) as caught:
        _ = await workflow.build_transition_blocker_list(subject, "404 Not Found")

    assert str(caught.value) == 'Transition "404 Not Found" is not defined for workflow "unnamed".'


@pytest.mark.parametrize(
    ("marking", "transition_name", "blocked"),
    [
        (None, "t1", False),
        (None, "t2", True),
        ({"b": 1}, "t1", True),
        ({"b": 1}, "t2", True),
        ({"b": 1, "c": 1}, "t1", True),
        ({"b": 1, "c": 1}, "t2", False),
        ({"f": 1}, "t5", True),
        ({"f": 1}, "t6", False),
    ],
)
async def test_build_transition_blocker_list_is_empty_only_for_an_enabled_transition(
    subject: AnySubject,
    marking: Mapping[str, int] | None,
    transition_name: str,
    blocked: bool,
) -> None:
    await keep(subject, marking)
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())

    blockers = await workflow.build_transition_blocker_list(subject, transition_name)

    assert blockers.is_empty() is not blocked


async def test_build_transition_blocker_list_gives_the_marking_as_the_reason(
    subject: AnySubject,
) -> None:
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())

    [blocker] = await workflow.build_transition_blocker_list(subject, "t2")

    assert blocker.get_message() == "The marking does not enable the transition."
    assert blocker.get_code() == MARKING_CODE


async def test_build_transition_blocker_list_gives_the_reasons_of_the_guards(
    subject: AnySubject,
) -> None:
    dispatcher = EventDispatcher()
    workflow = Workflow(create_simple_workflow_definition(), MethodMarkingStore(), dispatcher)

    def first(event: GuardEvent) -> None:
        event.add_transition_blocker(TransitionBlocker("Transition blocker 1", "blocker_1"))
        event.add_transition_blocker(TransitionBlocker("Transition blocker 2", "blocker_2"))

    def second(event: GuardEvent) -> None:
        event.add_transition_blocker(TransitionBlocker("Transition blocker 3", "blocker_3"))

    def fourth(event: GuardEvent) -> None:
        event.set_blocked(True, "You should not pass !!")

    dispatcher.add_listener("workflow.guard", first)
    dispatcher.add_listener("workflow.guard", second)
    dispatcher.add_listener("workflow.guard", _Guard().block)
    dispatcher.add_listener("workflow.guard", fourth)

    blockers = list(await workflow.build_transition_blocker_list(subject, "t1"))

    assert [(blocker.get_message(), blocker.get_code()) for blocker in blockers] == [
        ("Transition blocker 1", "blocker_1"),
        ("Transition blocker 2", "blocker_2"),
        ("Transition blocker 3", "blocker_3"),
        (
            "The transition has been blocked by a guard (tests.unit.test_workflow._Guard).",
            UNKNOWN_CODE,
        ),
        ("You should not pass !!", UNKNOWN_CODE),
    ]


# Applying a transition.


async def test_apply_of_an_undefined_transition_raises_with_the_context(
    subject: AnySubject,
) -> None:
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())
    context = {"lorem": "ipsum"}

    with pytest.raises(UndefinedTransitionError) as caught:
        _ = await workflow.apply(subject, "404 Not Found", context)

    assert str(caught.value) == 'Transition "404 Not Found" is not defined for workflow "unnamed".'
    assert caught.value.get_context() == context


async def test_apply_of_a_blocked_transition_raises_with_its_blockers(
    subject: AnySubject,
) -> None:
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())
    context = {"lorem": "ipsum"}

    with pytest.raises(NotEnabledTransitionError) as caught:
        _ = await workflow.apply(subject, "t2", context)

    error = caught.value
    [blocker] = error.get_transition_blocker_list()
    assert str(error) == 'Cannot apply transition "t2" on workflow "unnamed".'
    assert blocker.get_message() == "The marking does not enable the transition."
    assert error.get_workflow() is workflow
    assert error.get_subject() is subject
    assert error.get_transition_name() == "t2"
    assert error.get_context() == context


async def test_apply_moves_the_tokens(subject: AnySubject) -> None:
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())

    marking = await workflow.apply(subject, "t1")

    assert not marking.has("a")
    assert marking.has("b")
    assert marking.has("c")


async def test_apply_fires_every_enabled_transition_of_the_name(subject: AnySubject) -> None:
    workflow = Workflow(create_workflow_with_same_name_transition(), MethodMarkingStore())

    after_split = await workflow.apply(subject, "a_to_bc")
    after_both_back = _sorted_places(await workflow.apply(subject, "to_a"))
    _ = await workflow.apply(subject, "a_to_bc")
    after_join = _sorted_places(await workflow.apply(subject, "b_to_c"))
    after_one_back = _sorted_places(await workflow.apply(subject, "to_a"))

    assert _sorted_places(after_split) == [("b", 1), ("c", 1)]
    # Two tokens in "a".
    assert after_both_back == [("a", 2)]
    assert after_join == [("a", 1), ("c", 2)]
    assert after_one_back == [("a", 2), ("c", 1)]


async def test_apply_fires_same_named_transitions_leaving_different_places(
    subject: AnySubject,
) -> None:
    await keep(subject, {"a": 1, "b": 1})
    definition = Definition(list("abcd"), [Transition("t", "a", "c"), Transition("t", "b", "d")])
    workflow = Workflow(definition, MethodMarkingStore())

    marking = await workflow.apply(subject, "t")

    assert _sorted_places(marking) == [("c", 1), ("d", 1)]


async def test_apply_fires_only_the_transitions_enabled_before_it_moves(
    subject: AnySubject,
) -> None:
    await keep(subject, {"a": 1})
    definition = Definition(
        list("abcd"),
        [Transition("t", "a", "b"), Transition("t", "b", "c"), Transition("t", "c", "d")],
    )
    workflow = Workflow(definition, MethodMarkingStore())

    marking = await workflow.apply(subject, "t")

    # Not chained through to "d".
    assert _sorted_places(marking) == [("b", 1)]


@pytest.mark.parametrize("transition_name", ["back1", "back2"])
async def test_apply_moves_back_through_same_named_transitions(
    subject: AnySubject, transition_name: str
) -> None:
    workflow = Workflow(create_workflow_with_same_name_back_transition(), MethodMarkingStore())

    steps = [
        _sorted_places(await workflow.apply(subject, name))
        for name in ("a_to_bc", transition_name, transition_name, "a_to_bc", "c_to_cb", "c_to_cb")
    ]

    assert steps == [
        [("b", 1), ("c", 1)],
        [("a", 1), ("b", 1)],
        [("a", 2)],
        [("a", 1), ("b", 1), ("c", 1)],
        [("a", 1), ("b", 2), ("c", 1)],
        [("a", 1), ("b", 3), ("c", 1)],
    ]


async def test_apply_hands_the_store_the_context_a_listener_extended(
    subject: AnySubject,
) -> None:
    dispatcher = EventDispatcher()

    def add_user(event: TransitionEvent) -> None:
        event.set_context({**event.get_context(), "user": "admin"})

    dispatcher.add_listener("workflow.transition", add_user)
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore(), dispatcher)

    _ = await workflow.apply(subject, "t1", {"foo": "bar"})

    assert subject.get_context() == {"foo": "bar", "user": "admin"}


async def test_apply_moves_tokens_by_the_weight_of_each_arc(subject: AnySubject) -> None:
    definition = Definition(
        [],
        [
            Transition(
                "start", "init", [Arc("prepare_leg", 4), "prepare_top", "stopwatch_running"]
            ),
            Transition("build_leg", "prepare_leg", "leg_created"),
            Transition("build_top", "prepare_top", "top_created"),
            Transition(
                "join", [Arc("leg_created", 4), "top_created", "stopwatch_running"], "finished"
            ),
        ],
    )
    workflow = Workflow(definition)
    names = ("start", "build_leg", "build_top", "join")

    async def enabled() -> list[bool]:
        return [await workflow.can(subject, name) for name in names]

    assert await enabled() == [True, False, False, False]

    _ = await workflow.apply(subject, "start")
    assert await _kept_places(subject) == [
        ("prepare_leg", 4),
        ("prepare_top", 1),
        ("stopwatch_running", 1),
    ]
    assert await enabled() == [False, True, True, False]

    _ = await workflow.apply(subject, "build_leg")
    assert await _kept_places(subject) == [
        ("prepare_leg", 3),
        ("prepare_top", 1),
        ("stopwatch_running", 1),
        ("leg_created", 1),
    ]
    assert await enabled() == [False, True, True, False]

    _ = await workflow.apply(subject, "build_top")
    assert await _kept_places(subject) == [
        ("prepare_leg", 3),
        ("stopwatch_running", 1),
        ("leg_created", 1),
        ("top_created", 1),
    ]
    assert await enabled() == [False, True, False, False]

    _ = await workflow.apply(subject, "build_leg")
    assert await _kept_places(subject) == [
        ("prepare_leg", 2),
        ("stopwatch_running", 1),
        ("leg_created", 2),
        ("top_created", 1),
    ]
    assert await enabled() == [False, True, False, False]

    _ = await workflow.apply(subject, "build_leg")
    _ = await workflow.apply(subject, "build_leg")
    assert await _kept_places(subject) == [
        ("stopwatch_running", 1),
        ("leg_created", 4),
        ("top_created", 1),
    ]
    assert await enabled() == [False, False, False, True]

    _ = await workflow.apply(subject, "join")
    assert await _kept_places(subject) == [("finished", 1)]


# The events applying a transition dispatches.


async def test_apply_dispatches_every_event_in_order(subject: AnySubject) -> None:
    dispatcher = EventDispatcherSpy()
    workflow = Workflow(
        create_complex_workflow_definition(), MethodMarkingStore(), dispatcher, NAME
    )

    _ = await workflow.apply(subject, "t1")

    assert dispatcher.dispatched_event_names == [
        "workflow.entered",
        "workflow.workflow_name.entered",
        "workflow.workflow_name.entered.a",
        "workflow.guard",
        "workflow.workflow_name.guard",
        "workflow.workflow_name.guard.t1",
        "workflow.leave",
        "workflow.workflow_name.leave",
        "workflow.workflow_name.leave.a",
        "workflow.transition",
        "workflow.workflow_name.transition",
        "workflow.workflow_name.transition.t1",
        "workflow.enter",
        "workflow.workflow_name.enter",
        "workflow.workflow_name.enter.b",
        "workflow.workflow_name.enter.c",
        "workflow.entered",
        "workflow.workflow_name.entered",
        "workflow.workflow_name.entered.b",
        "workflow.workflow_name.entered.c",
        "workflow.completed",
        "workflow.workflow_name.completed",
        "workflow.workflow_name.completed.t1",
        # Announcing guards every transition enabled after the move.
        "workflow.announce",
        "workflow.workflow_name.announce",
        "workflow.guard",
        "workflow.workflow_name.guard",
        "workflow.workflow_name.guard.t2",
        "workflow.workflow_name.announce.t2",
    ]


@pytest.mark.parametrize(
    ("context", "fired"),
    [
        ({Workflow.DISABLE_ANNOUNCE_EVENT: True}, False),
        ({Workflow.DISABLE_ANNOUNCE_EVENT: False}, True),
        ({}, True),
    ],
)
async def test_apply_announces_unless_the_context_disables_it(
    subject: AnySubject, context: Mapping[str, object], fired: bool
) -> None:
    dispatcher = EventDispatcherSpy()
    workflow = Workflow(
        create_complex_workflow_definition(), MethodMarkingStore(), dispatcher, NAME
    )

    _ = await workflow.apply(subject, "t1", context)

    assert ("workflow.workflow_name.announce" in dispatcher.dispatched_event_names) is fired


async def test_apply_dispatches_only_the_events_its_context_leaves_enabled(
    subject: AnySubject,
) -> None:
    dispatcher = EventDispatcherSpy()
    workflow = Workflow(_two_transitions_from_a(), MethodMarkingStore(), dispatcher, NAME)

    _ = await workflow.apply(
        subject,
        "a-b",
        {
            Workflow.DISABLE_LEAVE_EVENT: True,
            Workflow.DISABLE_ENTER_EVENT: True,
            Workflow.DISABLE_ENTERED_EVENT: True,
            Workflow.DISABLE_COMPLETED_EVENT: True,
            Workflow.DISABLE_ANNOUNCE_EVENT: True,
        },
    )

    assert dispatcher.dispatched_event_names == [
        "workflow.guard",
        "workflow.workflow_name.guard",
        "workflow.workflow_name.guard.a-b",
        "workflow.transition",
        "workflow.workflow_name.transition",
        "workflow.workflow_name.transition.a-b",
    ]


async def test_apply_still_moves_the_tokens_when_every_event_is_disabled(
    subject: AnySubject,
) -> None:
    workflow = Workflow(_two_transitions_from_a(), MethodMarkingStore(), EventDispatcherSpy(), NAME)

    marking = await workflow.apply(
        subject,
        "a-b",
        {
            Workflow.DISABLE_LEAVE_EVENT: True,
            Workflow.DISABLE_TRANSITION_EVENT: True,
            Workflow.DISABLE_ENTER_EVENT: True,
        },
    )

    assert _sorted_places(marking) == [("b", 1)]


async def test_apply_keeps_the_context_when_the_transition_event_is_disabled(
    subject: AnySubject,
) -> None:
    dispatcher = EventDispatcher()

    def clear_context(event: TransitionEvent) -> None:
        event.set_context({})

    dispatcher.add_listener("workflow.transition", clear_context)
    workflow = Workflow(_two_transitions_from_a(), MethodMarkingStore(), dispatcher, NAME)
    context = {Workflow.DISABLE_TRANSITION_EVENT: True, "lorem": "ipsum"}

    marking = await workflow.apply(subject, "a-b", context)

    assert marking.get_context() == context


async def test_apply_dispatches_only_the_guard_when_no_event_is_to_be_dispatched(
    subject: AnySubject,
) -> None:
    dispatcher = EventDispatcherSpy()
    workflow = Workflow(_two_transitions_from_a(), MethodMarkingStore(), dispatcher, NAME, [])

    _ = await workflow.apply(subject, "a-b")

    assert dispatcher.dispatched_event_names == [
        "workflow.guard",
        "workflow.workflow_name.guard",
        "workflow.workflow_name.guard.a-b",
    ]


async def test_apply_dispatches_the_guard_and_the_events_allowed(subject: AnySubject) -> None:
    dispatcher = EventDispatcherSpy()
    workflow = Workflow(
        _two_transitions_from_a(),
        MethodMarkingStore(),
        dispatcher,
        NAME,
        [WorkflowEvents.COMPLETED],
    )

    _ = await workflow.apply(subject, "a-b")

    assert dispatcher.dispatched_event_names == [
        "workflow.guard",
        "workflow.workflow_name.guard",
        "workflow.workflow_name.guard.a-b",
        "workflow.completed",
        "workflow.workflow_name.completed",
        "workflow.workflow_name.completed.a-b",
    ]


async def test_apply_dispatches_every_event_but_those_blocked(subject: AnySubject) -> None:
    dispatcher = EventDispatcherSpy()
    # Every event but the announce, including any event added later.
    workflow = Workflow(
        create_complex_workflow_definition(),
        MethodMarkingStore(),
        dispatcher,
        NAME,
        [f"!{WorkflowEvents.ANNOUNCE}"],
    )

    _ = await workflow.apply(subject, "t1")
    _ = await workflow.apply(subject, "t2")

    names = [str(name) for name in dispatcher.dispatched_event_names]
    # An allow-list read literally would dispatch nothing and pass the last check vacuously.
    assert "workflow.workflow_name.transition" in names
    assert [name for name in names if "announce" in name] == []


def test_blocking_the_guard_event_raises() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = Workflow(
            create_complex_workflow_definition(),
            MethodMarkingStore(),
            EventDispatcherSpy(),
            NAME,
            [f"!{WorkflowEvents.GUARD}"],
        )

    assert str(caught.value) == (
        'The "workflow.guard" event cannot be disabled in events_to_dispatch for workflow '
        '"workflow_name": it is always dispatched.'
    )


def test_mixing_allowed_and_blocked_events_raises() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = Workflow(
            create_complex_workflow_definition(),
            MethodMarkingStore(),
            EventDispatcherSpy(),
            "mixed",
            [WorkflowEvents.COMPLETED, f"!{WorkflowEvents.ANNOUNCE}"],
        )

    assert str(caught.value) == (
        'Cannot mix allow-list and block-list entries in events_to_dispatch for workflow "mixed": '
        'every entry must start with "!" (block-list mode) or none of them must '
        "(allow-list mode)."
    )


async def test_apply_announces_no_transition_when_none_is_enabled_after_the_move(
    subject: AnySubject,
) -> None:
    dispatcher = EventDispatcherSpy()
    workflow = Workflow(_two_transitions_from_a(), MethodMarkingStore(), dispatcher, NAME)

    _ = await workflow.apply(subject, "a-b")

    assert dispatcher.dispatched_event_names == [
        "workflow.entered",
        "workflow.workflow_name.entered",
        "workflow.workflow_name.entered.a",
        "workflow.guard",
        "workflow.workflow_name.guard",
        "workflow.workflow_name.guard.a-b",
        "workflow.leave",
        "workflow.workflow_name.leave",
        "workflow.workflow_name.leave.a",
        "workflow.transition",
        "workflow.workflow_name.transition",
        "workflow.workflow_name.transition.a-b",
        "workflow.enter",
        "workflow.workflow_name.enter",
        "workflow.workflow_name.enter.b",
        "workflow.entered",
        "workflow.workflow_name.entered",
        "workflow.workflow_name.entered.b",
        "workflow.completed",
        "workflow.workflow_name.completed",
        "workflow.workflow_name.completed.a-b",
        "workflow.announce",
        "workflow.workflow_name.announce",
    ]


async def test_every_event_names_the_workflow(subject: AnySubject) -> None:
    dispatcher = EventDispatcher()
    workflow = Workflow(
        create_complex_workflow_definition(), MethodMarkingStore(), dispatcher, NAME
    )
    named: list[str] = []

    def record(event: Event) -> None:
        named.append(event.get_workflow_name())

    for event_name in (
        "workflow.guard",
        "workflow.leave",
        "workflow.transition",
        "workflow.enter",
        "workflow.entered",
        "workflow.announce",
    ):
        dispatcher.add_listener(event_name, record)

    _ = await workflow.apply(subject, "t1")

    # The initial entered, guarding t1, leave, transition, enter, entered,
    # announce, and guarding t2 for it.
    assert named == [NAME] * 8


async def test_every_event_carries_the_context_of_the_call(subject: AnySubject) -> None:
    dispatcher = EventDispatcher()
    workflow = Workflow(
        create_complex_workflow_definition(), MethodMarkingStore(), dispatcher, NAME
    )
    context = {"context": True}
    seen: list[dict[str, object]] = []

    def record(event: _ContextEvent) -> None:
        seen.append(event.get_context())

    for event_name in (
        "workflow.leave",
        "workflow.transition",
        "workflow.enter",
        "workflow.entered",
        "workflow.announce",
    ):
        dispatcher.add_listener(event_name, record)

    _ = await workflow.apply(subject, "t1", context)

    # The initial entered, leave, transition, enter, entered, announce.
    assert seen == [context] * 6


async def test_apply_returns_a_marking_carrying_the_context(subject: AnySubject) -> None:
    workflow = Workflow(
        create_complex_workflow_definition(), MethodMarkingStore(), EventDispatcher(), NAME
    )
    context = {"context": True}

    marking = await workflow.apply(subject, "t1", context)

    assert marking.get_context() == context


async def test_apply_returns_a_marking_carrying_the_context_a_listener_set(
    subject: AnySubject,
) -> None:
    dispatcher = EventDispatcher()
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore(), dispatcher)

    def replace_context(event: TransitionEvent) -> None:
        event.set_context({"foo": "bar"})

    dispatcher.add_listener("workflow.transition", replace_context)

    marking = await workflow.apply(subject, "t1", {"initial": "value"})

    assert marking.get_context() == {"foo": "bar"}


async def test_the_initial_entered_event_carries_the_default_initial_context(
    subject: AnySubject,
) -> None:
    dispatcher = EventDispatcher()
    workflow = Workflow(
        create_complex_workflow_definition(), MethodMarkingStore(), dispatcher, NAME
    )
    seen: list[dict[str, object]] = []

    def record(event: EnteredEvent) -> None:
        seen.append(event.get_context())

    dispatcher.add_listener(f"workflow.{NAME}.entered.a", record)

    _ = await workflow.apply(subject, "t1")

    assert seen == [{"initial": True}]


async def test_entered_is_dispatched_for_the_places_the_transition_enters_only(
    subject: AnySubject,
) -> None:
    definition = Definition(
        ["init", "A", "B", "C"],
        [
            Transition("from_init_to_a_and_b", "init", ["A", "B"]),
            Transition("from_b_to_c", "B", "C"),
        ],
    )
    dispatcher = EventDispatcher()
    workflow = Workflow(definition, MethodMarkingStore(), dispatcher, NAME)
    entered: list[Event] = []
    dispatcher.add_listener(f"workflow.{NAME}.entered.A", entered.append)

    _ = await workflow.apply(subject, "from_init_to_a_and_b")
    _ = await workflow.apply(subject, "from_b_to_c")

    [event] = entered
    assert isinstance(event, EnteredEvent)
    assert event.get_transition() is definition.get_transitions()[0]


async def test_events_see_the_marking_of_the_step_they_announce(subject: AnySubject) -> None:
    definition = Definition(list("abcdef"), [Transition("t", list("abc"), list("def"))])
    await keep(subject, {"a": 1, "b": 1, "c": 1})
    dispatcher = EventDispatcher()
    workflow = Workflow(definition, MethodMarkingStore(), dispatcher, "test")
    seen: list[dict[str, int]] = []

    def record(event: Event) -> None:
        seen.append(event.get_marking().get_places())

    for event_name in (
        "workflow.leave",
        "workflow.test.leave",
        "workflow.test.leave.a",
        "workflow.test.leave.b",
        "workflow.test.leave.c",
        "workflow.transition",
        "workflow.test.transition",
        "workflow.test.transition.t",
        "workflow.enter",
        "workflow.test.enter",
        "workflow.test.enter.d",
        "workflow.test.enter.e",
        "workflow.test.enter.f",
    ):
        dispatcher.add_listener(event_name, record)

    _ = await workflow.apply(subject, "t")

    # Leaving sees the places left; the transition and entering see none yet.
    assert seen == [{"a": 1, "b": 1, "c": 1}] * 5 + [{}] * 8


# Listing the enabled transitions.


@pytest.mark.parametrize(
    ("marking", "expected"),
    [
        (None, []),
        ({"d": 1}, ["t3", "t4"]),
        ({"c": 1, "e": 1}, ["t5"]),
    ],
)
async def test_get_enabled_transitions_lists_those_neither_marking_nor_guard_blocks(
    subject: AnySubject, marking: Mapping[str, int] | None, expected: list[str]
) -> None:
    await keep(subject, marking)
    dispatcher = EventDispatcher()
    dispatcher.add_listener(f"workflow.{NAME}.guard.t1", _block)
    workflow = Workflow(
        create_complex_workflow_definition(), MethodMarkingStore(), dispatcher, NAME
    )

    transitions = await workflow.get_enabled_transitions(subject)

    assert [transition.get_name() for transition in transitions] == expected


@pytest.mark.parametrize(
    ("marking", "expected"),
    [
        (None, ["a_to_bc"]),
        ({"b": 1, "c": 1}, ["b_to_c", "to_a", "to_a"]),
    ],
)
async def test_get_enabled_transitions_lists_each_same_named_transition(
    subject: AnySubject, marking: Mapping[str, int] | None, expected: list[str]
) -> None:
    await keep(subject, marking)
    workflow = Workflow(create_workflow_with_same_name_transition(), MethodMarkingStore())

    transitions = await workflow.get_enabled_transitions(subject)

    assert [transition.get_name() for transition in transitions] == expected


async def test_get_enabled_transition_returns_the_transition_of_the_name(
    subject: AnySubject,
) -> None:
    await keep(subject, {"d": 1})
    definition = create_complex_workflow_definition()
    workflow = Workflow(definition, MethodMarkingStore())

    transition = await workflow.get_enabled_transition(subject, "t3")

    assert transition is definition.get_transitions()[2]


async def test_get_enabled_transition_of_an_undefined_name_is_none(subject: AnySubject) -> None:
    await keep(subject, {"d": 1})
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())

    assert await workflow.get_enabled_transition(subject, "does_not_exist") is None


async def test_get_enabled_transition_of_a_blocked_name_is_none(subject: AnySubject) -> None:
    await keep(subject, {"d": 1})
    workflow = Workflow(create_complex_workflow_definition(), MethodMarkingStore())

    assert await workflow.get_enabled_transition(subject, "t1") is None
