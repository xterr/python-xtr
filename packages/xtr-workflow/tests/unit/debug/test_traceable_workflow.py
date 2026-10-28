"""The traceable workflow records every call that may ask listeners, answering as the one it wraps.

A record tells the method called, how long it took, the arguments, the marking
a subject was in before ``apply``, and what came back — or what was raised,
which is raised on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from xtr_clock import MockClock, MonotonicClock
from xtr_event_dispatcher import EventDispatcher
from xtr_service_contracts import ResetInterface

from tests.fixtures.subject import Subject
from xtr_workflow import Definition, Marking, Transition, Workflow, WorkflowInterface
from xtr_workflow.debug import TraceableWorkflow
from xtr_workflow.exception import LogicError

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface

pytestmark = pytest.mark.anyio


def _workflow(dispatcher: EventDispatcherInterface | None = None) -> Workflow:
    """Return a workflow publishing a draft; a subject in no place yet is a draft."""
    return Workflow(
        Definition(["draft", "published"], [Transition("publish", "draft", "published")]),
        dispatcher=dispatcher,
        name="article",
    )


def test_it_is_a_workflow_that_can_be_reset() -> None:
    traceable = TraceableWorkflow(_workflow())

    assert isinstance(traceable, WorkflowInterface)
    assert isinstance(traceable, ResetInterface)


async def test_get_marking_is_recorded_with_the_marking_it_returned() -> None:
    traceable = TraceableWorkflow(_workflow(), MockClock())
    subject = Subject()
    context = {"initial": False}

    marking = await traceable.get_marking(subject, context)

    assert marking.get_places() == {"draft": 1}
    assert traceable.get_calls() == [
        {
            "method": "get_marking",
            "duration": 0.0,
            "args": (subject, context),
            "previous_marking": None,
            "return": marking,
        }
    ]


async def test_can_is_recorded_with_its_answer() -> None:
    traceable = TraceableWorkflow(_workflow(), MockClock())
    subject = Subject()

    answer = await traceable.can(subject, "publish")

    assert answer is True
    assert traceable.get_calls() == [
        {
            "method": "can",
            "duration": 0.0,
            "args": (subject, "publish"),
            "previous_marking": None,
            "return": True,
        }
    ]


async def test_build_transition_blocker_list_is_recorded_with_the_list_it_returned() -> None:
    traceable = TraceableWorkflow(_workflow(), MockClock())
    subject = Subject()

    blockers = await traceable.build_transition_blocker_list(subject, "publish")

    assert blockers.is_empty()
    assert traceable.get_calls() == [
        {
            "method": "build_transition_blocker_list",
            "duration": 0.0,
            "args": (subject, "publish"),
            "previous_marking": None,
            "return": blockers,
        }
    ]


async def test_apply_is_recorded_with_the_marking_the_subject_was_in_before() -> None:
    traceable = TraceableWorkflow(_workflow(), MockClock())
    subject = Subject({"draft": 1})
    context = {"by": "editor"}

    marking = await traceable.apply(subject, "publish", context)

    [call] = traceable.get_calls()
    assert cast("Marking", call["previous_marking"]).get_places() == {"draft": 1}
    assert {key: value for key, value in call.items() if key != "previous_marking"} == {
        "method": "apply",
        "duration": 0.0,
        "args": (subject, "publish", context),
        "return": marking,
    }


async def test_apply_moves_the_subject_through_the_wrapped_workflow_with_its_context() -> None:
    traceable = TraceableWorkflow(_workflow(), MockClock())
    subject = Subject({"draft": 1})

    marking = await traceable.apply(subject, "publish", {"by": "editor"})

    assert marking.get_places() == {"published": 1}
    assert (subject.get_marking(), subject.get_context()) == ({"published": 1}, {"by": "editor"})


async def test_get_enabled_transitions_is_recorded_with_the_transitions_it_returned() -> None:
    workflow = _workflow()
    traceable = TraceableWorkflow(workflow, MockClock())
    subject = Subject()

    transitions = await traceable.get_enabled_transitions(subject)

    assert transitions == workflow.get_definition().get_transitions()
    assert traceable.get_calls() == [
        {
            "method": "get_enabled_transitions",
            "duration": 0.0,
            "args": (subject,),
            "previous_marking": None,
            "return": transitions,
        }
    ]


async def test_get_enabled_transition_is_recorded_with_the_transition_it_returned() -> None:
    workflow = _workflow()
    traceable = TraceableWorkflow(workflow, MockClock())
    subject = Subject()

    transition = await traceable.get_enabled_transition(subject, "publish")

    assert transition is workflow.get_definition().get_transitions()[0]
    assert traceable.get_calls() == [
        {
            "method": "get_enabled_transition",
            "duration": 0.0,
            "args": (subject, "publish"),
            "previous_marking": None,
            "return": transition,
        }
    ]


async def test_an_error_is_recorded_then_raised_on() -> None:
    traceable = TraceableWorkflow(_workflow(), MockClock())
    subject = object()

    with pytest.raises(LogicError) as raised:
        _ = await traceable.can(subject, "publish")

    assert traceable.get_calls() == [
        {
            "method": "can",
            "duration": 0.0,
            "args": (subject, "publish"),
            "previous_marking": None,
            "exception": raised.value,
        }
    ]


async def test_apply_records_no_marking_before_when_none_can_be_read() -> None:
    traceable = TraceableWorkflow(_workflow(), MockClock())
    subject = object()

    with pytest.raises(LogicError) as raised:
        _ = await traceable.apply(subject, "publish")

    assert traceable.get_calls() == [
        {
            "method": "apply",
            "duration": 0.0,
            "args": (subject, "publish", None),
            "previous_marking": None,
            "exception": raised.value,
        }
    ]


async def test_the_duration_is_how_long_the_call_took_in_milliseconds() -> None:
    clock = MockClock()
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.guard", lambda: clock.sleep(0.25))
    traceable = TraceableWorkflow(_workflow(dispatcher), clock)

    _ = await traceable.can(Subject(), "publish")

    assert [call["duration"] for call in traceable.get_calls()] == [250.0]


async def test_a_call_made_while_disabled_reaches_the_workflow_unrecorded() -> None:
    traceable = TraceableWorkflow(_workflow(), MockClock(), lambda: True)

    marking = await traceable.apply(Subject(), "publish")

    assert marking.get_places() == {"published": 1}
    assert traceable.get_calls() == []


async def test_disabled_is_asked_before_each_call() -> None:
    answers = iter([True, False])
    traceable = TraceableWorkflow(_workflow(), MockClock(), lambda: next(answers))
    subject = Subject()
    _ = await traceable.can(subject, "publish")

    _ = await traceable.get_enabled_transitions(subject)

    assert [call["method"] for call in traceable.get_calls()] == ["get_enabled_transitions"]


async def test_reset_forgets_every_call_recorded() -> None:
    traceable = TraceableWorkflow(_workflow(), MockClock())
    _ = await traceable.can(Subject(), "publish")

    await traceable.reset()

    assert traceable.get_calls() == []


async def test_the_calls_returned_are_a_list_of_their_own() -> None:
    traceable = TraceableWorkflow(_workflow(), MockClock())
    calls = traceable.get_calls()

    _ = await traceable.can(Subject(), "publish")

    assert calls == []


def test_the_accessors_answer_as_the_wrapped_workflow_unrecorded() -> None:
    workflow = _workflow()
    traceable = TraceableWorkflow(workflow, MockClock())

    answers = (
        traceable.get_name(),
        traceable.get_definition(),
        traceable.get_marking_store(),
        traceable.get_metadata_store(),
    )

    assert answers == (
        workflow.get_name(),
        workflow.get_definition(),
        workflow.get_marking_store(),
        workflow.get_metadata_store(),
    )
    assert traceable.get_calls() == []


def test_get_inner_returns_the_wrapped_workflow() -> None:
    workflow = _workflow()

    assert TraceableWorkflow(workflow).get_inner() is workflow


def test_calls_are_timed_by_a_monotonic_clock_unless_given_another() -> None:
    assert isinstance(TraceableWorkflow(_workflow())._clock, MonotonicClock)
