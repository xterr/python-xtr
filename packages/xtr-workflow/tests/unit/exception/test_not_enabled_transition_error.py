"""A transition the marking or a guard blocks cannot be applied."""

from __future__ import annotations

from tests.support.workflow_stub import WorkflowStub as _Workflow
from xtr_workflow import TransitionBlockerList
from xtr_workflow.exception import NotEnabledTransitionError


def test_it_names_the_transition_and_the_workflow() -> None:
    error = NotEnabledTransitionError(object(), "t2", _Workflow(), TransitionBlockerList())

    assert str(error) == 'Cannot apply transition "t2" on workflow "article".'


def test_it_keeps_what_blocks_the_transition() -> None:
    blockers = TransitionBlockerList()

    error = NotEnabledTransitionError(object(), "t2", _Workflow(), blockers)

    assert error.get_transition_blocker_list() is blockers


def test_it_keeps_the_call_it_was_raised_for() -> None:
    subject = object()
    workflow = _Workflow()

    error = NotEnabledTransitionError(
        subject, "t2", workflow, TransitionBlockerList(), {"lorem": "ipsum"}
    )

    assert error.get_subject() is subject
    assert error.get_transition_name() == "t2"
    assert error.get_workflow() is workflow
    assert error.get_context() == {"lorem": "ipsum"}
