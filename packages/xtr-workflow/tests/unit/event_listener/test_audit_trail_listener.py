"""The audit trail logs each place a subject leaves and enters, and each transition it takes."""

from __future__ import annotations

from typing import get_type_hints

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_logging import Logger, TestHandler
from xtr_logging_contracts import Level, LoggerInterface, NullLogger

from tests.fixtures.subject import Subject
from tests.support.definitions import create_simple_workflow_definition
from tests.support.workflow_stub import WorkflowStub
from xtr_workflow import Definition, Marking, Transition, Workflow
from xtr_workflow.event import Event, TransitionEvent
from xtr_workflow.event_listener import AuditTrailListener
from xtr_workflow.exception import LogicError
from xtr_workflow.marking_store import MethodMarkingStore

SUBJECT_CLASS = "tests.fixtures.subject.Subject"


def _audited(definition: Definition, handler: TestHandler) -> Workflow:
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(AuditTrailListener(Logger("workflow", [handler])))
    return Workflow(definition, MethodMarkingStore(), dispatcher)


@pytest.mark.anyio
async def test_it_logs_the_place_left_the_transition_taken_and_the_place_entered() -> None:
    handler = TestHandler()
    workflow = _audited(create_simple_workflow_definition(), handler)

    _ = await workflow.apply(Subject(), "t1")

    assert [(record.level, record.message, dict(record.context)) for record in handler.records] == [
        (
            Level.INFO,
            f'Leaving "a" for subject of class "{SUBJECT_CLASS}" in workflow "unnamed".',
            {},
        ),
        (
            Level.INFO,
            f'Transition "t1" for subject of class "{SUBJECT_CLASS}" in workflow "unnamed".',
            {},
        ),
        (
            Level.INFO,
            f'Entering "b" for subject of class "{SUBJECT_CLASS}" in workflow "unnamed".',
            {},
        ),
    ]


@pytest.mark.anyio
async def test_it_logs_one_line_for_each_place_left_and_each_place_entered() -> None:
    handler = TestHandler()
    definition = Definition(["a", "b", "c", "d"], [Transition("t1", ["a", "b"], ["c", "d"])])
    workflow = _audited(definition, handler)
    subject = Subject({"a": 1, "b": 1})

    _ = await workflow.apply(subject, "t1")

    assert [record.message for record in handler.records] == [
        f'Leaving "a" for subject of class "{SUBJECT_CLASS}" in workflow "unnamed".',
        f'Leaving "b" for subject of class "{SUBJECT_CLASS}" in workflow "unnamed".',
        f'Transition "t1" for subject of class "{SUBJECT_CLASS}" in workflow "unnamed".',
        f'Entering "c" for subject of class "{SUBJECT_CLASS}" in workflow "unnamed".',
        f'Entering "d" for subject of class "{SUBJECT_CLASS}" in workflow "unnamed".',
    ]


def test_an_event_carrying_no_transition_is_refused() -> None:
    listener = AuditTrailListener(NullLogger())
    event = TransitionEvent(Subject(), Marking(), None, WorkflowStub())

    with pytest.raises(LogicError) as raised:
        listener.on_transition(event)

    assert str(raised.value) == 'The "TransitionEvent" event carries no transition.'


def test_a_container_can_read_what_it_takes_and_what_it_listens_to() -> None:
    constructor = get_type_hints(AuditTrailListener.__init__)
    listener = get_type_hints(AuditTrailListener.on_leave)

    assert constructor["logger"] is LoggerInterface
    assert listener["event"] is Event
