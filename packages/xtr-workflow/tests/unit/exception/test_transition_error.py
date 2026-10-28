"""A transition error keeps the call it was raised for."""

from __future__ import annotations

from tests.support.workflow_stub import WorkflowStub as _Workflow
from xtr_workflow.exception import TransitionError


def test_it_reads_as_its_message() -> None:
    error = TransitionError(object(), "publish", _Workflow(), "Nope.")

    assert str(error) == "Nope."


def test_it_keeps_the_subject_the_transition_name_and_the_workflow() -> None:
    subject = object()
    workflow = _Workflow()

    error = TransitionError(subject, "publish", workflow, "Nope.")

    assert error.get_subject() is subject
    assert error.get_transition_name() == "publish"
    assert error.get_workflow() is workflow


def test_it_keeps_the_context_of_the_call() -> None:
    error = TransitionError(object(), "publish", _Workflow(), "Nope.", {"lorem": "ipsum"})

    assert error.get_context() == {"lorem": "ipsum"}


def test_its_context_is_empty_when_the_call_had_none() -> None:
    error = TransitionError(object(), "publish", _Workflow(), "Nope.")

    assert error.get_context() == {}
