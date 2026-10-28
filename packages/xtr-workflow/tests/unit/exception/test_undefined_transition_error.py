"""A transition the definition does not have cannot be applied."""

from __future__ import annotations

from tests.support.workflow_stub import WorkflowStub as _Workflow
from xtr_workflow.exception import UndefinedTransitionError


def test_it_names_the_transition_and_the_workflow() -> None:
    error = UndefinedTransitionError(object(), "404 Not Found", _Workflow())

    assert str(error) == 'Transition "404 Not Found" is not defined for workflow "article".'


def test_it_keeps_the_call_it_was_raised_for() -> None:
    subject = object()
    workflow = _Workflow()

    error = UndefinedTransitionError(subject, "404 Not Found", workflow, {"lorem": "ipsum"})

    assert error.get_subject() is subject
    assert error.get_transition_name() == "404 Not Found"
    assert error.get_workflow() is workflow
    assert error.get_context() == {"lorem": "ipsum"}
