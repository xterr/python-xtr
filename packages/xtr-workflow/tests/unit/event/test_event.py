"""A workflow event carries the subject, its marking, the transition and the workflow."""

from __future__ import annotations

import pytest
from xtr_event_dispatcher_contracts import Event as BaseEvent

from tests.support.workflow_stub import WorkflowStub
from xtr_workflow import Definition, Marking, Transition
from xtr_workflow.event import Event
from xtr_workflow.exception import LogicError
from xtr_workflow.metadata import InMemoryMetadataStore

TRANSITION = Transition("publish", "draft", "published")


def _workflow() -> WorkflowStub:
    metadata_store = InMemoryMetadataStore(
        {"title": "workflow title"},
        {"draft": {"title": "draft title"}},
        {TRANSITION: {"title": "publish title"}},
    )
    return WorkflowStub("post", Definition([], [TRANSITION], metadata_store=metadata_store))


def test_it_is_an_event_a_listener_can_stop() -> None:
    event = Event(object(), Marking())

    event.stop_propagation()

    assert isinstance(event, BaseEvent)
    assert event.is_propagation_stopped()


def test_it_keeps_what_it_is_built_with() -> None:
    subject = object()
    marking = Marking({"draft": 1})
    workflow = _workflow()

    event = Event(subject, marking, TRANSITION, workflow)

    assert event.get_subject() is subject
    assert event.get_marking() is marking
    assert event.get_transition() is TRANSITION
    assert event.get_workflow() is workflow


def test_its_transition_and_workflow_are_none_unless_given() -> None:
    event = Event(object(), Marking())

    assert event.get_transition() is None
    assert event.get_workflow() is None


def test_it_names_its_workflow() -> None:
    assert Event(object(), Marking(), workflow=_workflow()).get_workflow_name() == "post"


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        pytest.param(None, "workflow title", id="workflow"),
        pytest.param("draft", "draft title", id="place"),
        pytest.param(TRANSITION, "publish title", id="transition"),
        pytest.param("published", None, id="missing"),
    ],
)
def test_it_reads_metadata_from_the_store_of_its_workflow(
    subject: str | Transition | None,
    expected: str | None,
) -> None:
    event = Event(object(), Marking(), workflow=_workflow())

    assert event.get_metadata("title", subject) == expected


def test_naming_the_workflow_of_an_event_without_one_is_refused() -> None:
    event = Event(object(), Marking())

    with pytest.raises(LogicError) as raised:
        _ = event.get_workflow_name()

    assert str(raised.value) == 'The "Event" event carries no workflow.'


def test_reading_metadata_through_an_event_without_a_workflow_is_refused() -> None:
    event = Event(object(), Marking())

    with pytest.raises(LogicError) as raised:
        _ = event.get_metadata("title", None)

    assert str(raised.value) == 'The "Event" event carries no workflow.'
