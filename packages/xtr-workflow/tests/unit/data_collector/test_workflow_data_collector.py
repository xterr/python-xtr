"""The workflow collector keeps each call of the profiled request as plain data, and nothing else.

Calls reach it from a real traced workflow, the way the bundle wires one, so
what is asserted is what a profiled request would show.
"""

from __future__ import annotations

import json
from functools import partial
from typing import TYPE_CHECKING, cast

import anyio
import anyio.lowlevel
import pytest
from xtr_clock import MockClock
from xtr_event_dispatcher import EventDispatcher
from xtr_http_kernel.data_collector import (
    LateDataCollectorInterface,
    ProfiledRequest,
    TracingDataCollectorInterface,
)
from xtr_http_message import ServerRequest

from tests.fixtures.subject import Subject
from xtr_workflow import Definition, Transition, TransitionBlocker, Workflow
from xtr_workflow.data_collector import WorkflowDataCollector
from xtr_workflow.debug import TraceableWorkflow
from xtr_workflow.exception import UndefinedTransitionError

if TYPE_CHECKING:
    from xtr_workflow.event import GuardEvent

pytestmark = pytest.mark.anyio

_PROFILED = ProfiledRequest(ServerRequest("GET", "/"), 200, {}, {})
_DEFINED = [{"name": "article", "type": "workflow", "supports": ["app.Article"]}]


def _traced(
    collector: WorkflowDataCollector,
    dispatcher: EventDispatcher | None = None,
    clock: MockClock | None = None,
) -> TraceableWorkflow:
    """Return an ``article`` workflow publishing or rejecting a draft, traced into ``collector``."""
    workflow = Workflow(
        Definition(
            ["draft", "published", "rejected"],
            [
                Transition("publish", "draft", "published"),
                Transition("reject", "draft", "rejected"),
            ],
        ),
        dispatcher=dispatcher,
        name="article",
    )
    return TraceableWorkflow(
        workflow, clock or MockClock(), recorder=partial(collector.record, "article")
    )


def _calls(collector: WorkflowDataCollector) -> list[dict[str, object]]:
    data = collector.late_collect(collector.collect(_PROFILED), _PROFILED)
    return cast("list[dict[str, object]]", data["calls"])


def _guarded_by(expression: str) -> EventDispatcher:
    """Return a dispatcher whose guard blocks every transition, as a configured guard would."""
    dispatcher = EventDispatcher()

    def guard(event: GuardEvent) -> None:
        event.add_transition_blocker(
            TransitionBlocker.create_blocked_by_expression_guard_listener(expression)
        )

    dispatcher.add_listener("workflow.guard", guard)
    return dispatcher


def test_it_is_named_workflow() -> None:
    assert WorkflowDataCollector([]).name == "workflow"


def test_it_traces_requests_and_collects_late() -> None:
    collector = WorkflowDataCollector([])

    assert isinstance(collector, TracingDataCollectorInterface)
    assert isinstance(collector, LateDataCollectorInterface)


def test_collect_returns_the_defined_workflows() -> None:
    collector = WorkflowDataCollector(_DEFINED)

    assert collector.collect(_PROFILED) == {"workflows": _DEFINED}


def test_the_defined_workflows_returned_are_copies() -> None:
    collector = WorkflowDataCollector(_DEFINED)
    returned = cast("list[dict[str, object]]", collector.collect(_PROFILED)["workflows"])

    returned[0]["name"] = "changed"

    assert collector.collect(_PROFILED) == {"workflows": _DEFINED}


async def test_outside_a_profiled_request_no_call_is_kept() -> None:
    collector = WorkflowDataCollector([])
    traceable = _traced(collector)

    _ = await traceable.can(Subject(), "publish")

    assert _calls(collector) == []


async def test_a_call_made_before_the_request_began_is_not_kept() -> None:
    collector = WorkflowDataCollector([])
    traceable = _traced(collector)
    _ = await traceable.can(Subject(), "publish")

    collector.begin_request()

    assert _calls(collector) == []


async def test_can_is_kept_with_the_transition_and_its_answer() -> None:
    collector = WorkflowDataCollector([])
    traceable = _traced(collector)
    collector.begin_request()

    _ = await traceable.can(Subject(), "publish")

    assert _calls(collector) == [
        {
            "workflow": "article",
            "method": "can",
            "subject": "tests.fixtures.subject.Subject",
            "transition": "publish",
            "previous_marking": None,
            "marking": None,
            "result": True,
            "blocked": False,
            "duration_ms": 0.0,
            "error": None,
        }
    ]


async def test_can_answering_no_is_blocked() -> None:
    collector = WorkflowDataCollector([])
    traceable = _traced(collector)
    collector.begin_request()

    _ = await traceable.can(Subject({"published": 1}), "publish")

    [call] = _calls(collector)
    assert (call["result"], call["blocked"]) == (False, True)


async def test_apply_is_kept_with_the_places_before_and_after() -> None:
    collector = WorkflowDataCollector([])
    traceable = _traced(collector)
    collector.begin_request()

    _ = await traceable.apply(Subject({"draft": 1}), "publish")

    [call] = _calls(collector)
    assert (call["previous_marking"], call["marking"], call["result"], call["blocked"]) == (
        ["draft"],
        ["published"],
        None,
        False,
    )


async def test_a_blocked_apply_is_kept_with_what_blocked_it() -> None:
    collector = WorkflowDataCollector([])
    traceable = _traced(collector, _guarded_by("is_granted('ROLE_EDITOR')"))
    collector.begin_request()

    with pytest.raises(Exception, match="Cannot apply transition"):
        _ = await traceable.apply(Subject({"draft": 1}), "publish")

    [call] = _calls(collector)
    assert call["blocked"] is True
    assert call["marking"] is None
    assert call["result"] == [
        {
            "message": "The expression blocks the transition.",
            "code": TransitionBlocker.BLOCKED_BY_EXPRESSION_GUARD_LISTENER,
            "expression": "is_granted('ROLE_EDITOR')",
        }
    ]
    assert call["error"] == {
        "class": "xtr_workflow.exception.not_enabled_transition_error.NotEnabledTransitionError",
        "message": 'Cannot apply transition "publish" on workflow "article".',
    }


async def test_an_apply_that_failed_otherwise_is_an_error_not_a_block() -> None:
    collector = WorkflowDataCollector([])
    traceable = _traced(collector)
    collector.begin_request()

    with pytest.raises(UndefinedTransitionError):
        _ = await traceable.apply(Subject({"draft": 1}), "archive")

    [call] = _calls(collector)
    error = cast("dict[str, str]", call["error"])
    assert (call["blocked"], call["result"]) == (False, None)
    assert error["class"].endswith("UndefinedTransitionError")


async def test_a_blocker_list_is_kept_without_an_expression_when_it_names_none() -> None:
    collector = WorkflowDataCollector([])
    traceable = _traced(collector)
    collector.begin_request()

    _ = await traceable.build_transition_blocker_list(Subject({"published": 1}), "publish")

    [call] = _calls(collector)
    assert call["result"] == [
        {
            "message": "The marking does not enable the transition.",
            "code": TransitionBlocker.BLOCKED_BY_MARKING,
        }
    ]


async def test_the_enabled_transitions_are_kept_by_name() -> None:
    collector = WorkflowDataCollector([])
    traceable = _traced(collector)
    collector.begin_request()

    _ = await traceable.get_enabled_transitions(Subject({"draft": 1}))
    _ = await traceable.get_enabled_transition(Subject({"draft": 1}), "reject")
    _ = await traceable.get_enabled_transition(Subject({"published": 1}), "reject")

    assert [(call["transition"], call["result"]) for call in _calls(collector)] == [
        (None, ["publish", "reject"]),
        ("reject", ["reject"]),
        ("reject", []),
    ]


async def test_get_marking_is_kept_with_the_places_it_read() -> None:
    collector = WorkflowDataCollector([])
    traceable = _traced(collector)
    collector.begin_request()

    _ = await traceable.get_marking(Subject({"draft": 1}))

    [call] = _calls(collector)
    assert (call["transition"], call["marking"], call["result"]) == (None, ["draft"], None)


async def test_the_duration_is_kept_in_milliseconds() -> None:
    clock = MockClock()
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.guard", lambda: clock.sleep(0.25))
    collector = WorkflowDataCollector([])
    traceable = _traced(collector, dispatcher, clock)
    collector.begin_request()

    _ = await traceable.can(Subject(), "publish")

    assert [call["duration_ms"] for call in _calls(collector)] == [250.0]


async def test_a_call_is_kept_as_it_was_when_it_ended() -> None:
    collector = WorkflowDataCollector([])
    traceable = _traced(collector)
    subject = Subject({"draft": 1})
    collector.begin_request()
    _ = await traceable.get_marking(subject)

    _ = await traceable.apply(subject, "publish")

    assert [call["marking"] for call in _calls(collector)] == [["draft"], ["published"]]


async def test_late_collect_counts_the_calls_the_applied_and_the_blocked() -> None:
    collector = WorkflowDataCollector(_DEFINED)
    traceable = _traced(collector)
    collector.begin_request()
    _ = await traceable.can(Subject({"draft": 1}), "publish")
    _ = await traceable.can(Subject({"published": 1}), "publish")
    _ = await traceable.apply(Subject({"draft": 1}), "publish")

    data = collector.late_collect(collector.collect(_PROFILED), _PROFILED)

    assert data["workflows"] == _DEFINED
    assert data["counts"] == {"calls": 3, "applied": 1, "blocked": 1}


async def test_what_is_collected_is_plain_json() -> None:
    collector = WorkflowDataCollector(_DEFINED)
    traceable = _traced(collector, _guarded_by("subject.ready"))
    collector.begin_request()
    with pytest.raises(Exception, match="Cannot apply transition"):
        _ = await traceable.apply(Subject({"draft": 1}), "publish")

    data = collector.late_collect(collector.collect(_PROFILED), _PROFILED)

    assert json.loads(json.dumps(data)) == data


async def test_two_requests_served_at_once_each_see_only_their_own_calls() -> None:
    collector = WorkflowDataCollector([])
    traceable = _traced(collector)
    seen: dict[str, list[object]] = {}

    async def serve(transition: str) -> None:
        collector.begin_request()
        _ = await traceable.can(Subject({"draft": 1}), transition)
        await anyio.lowlevel.checkpoint()
        _ = await traceable.can(Subject({"draft": 1}), transition)
        seen[transition] = [call["transition"] for call in _calls(collector)]

    async with anyio.create_task_group() as group:
        _ = group.start_soon(serve, "publish")
        _ = group.start_soon(serve, "reject")

    assert seen == {"publish": ["publish", "publish"], "reject": ["reject", "reject"]}
