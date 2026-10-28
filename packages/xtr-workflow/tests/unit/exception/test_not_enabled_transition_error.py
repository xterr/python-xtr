"""A transition the marking or a guard blocks cannot be applied."""

from __future__ import annotations

from xtr_workflow.exception import NotEnabledTransitionError


class _Workflow:
    def get_name(self) -> str:
        return "article"


def test_it_names_the_transition_and_the_workflow() -> None:
    error = NotEnabledTransitionError(object(), "t2", _Workflow(), object())

    assert str(error) == 'Cannot apply transition "t2" on workflow "article".'


def test_it_keeps_what_blocks_the_transition() -> None:
    blockers = object()

    error = NotEnabledTransitionError(object(), "t2", _Workflow(), blockers)

    assert error.get_transition_blocker_list() is blockers


def test_it_keeps_the_call_it_was_raised_for() -> None:
    subject = object()
    workflow = _Workflow()

    error = NotEnabledTransitionError(subject, "t2", workflow, object(), {"lorem": "ipsum"})

    assert error.get_subject() is subject
    assert error.get_transition_name() == "t2"
    assert error.get_workflow() is workflow
    assert error.get_context() == {"lorem": "ipsum"}
