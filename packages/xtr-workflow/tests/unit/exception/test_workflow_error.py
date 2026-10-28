"""Every error this package defines derives from one, and from the standard error it stands for."""

from __future__ import annotations

import pytest

from xtr_workflow.exception import (
    InvalidArgumentError,
    InvalidDefinitionError,
    LogicError,
    NotEnabledTransitionError,
    TransitionError,
    UndefinedTransitionError,
    WorkflowError,
    WorkflowRuntimeError,
)


@pytest.mark.parametrize(
    ("error", "base"),
    [
        (WorkflowError, Exception),
        (InvalidArgumentError, WorkflowError),
        (InvalidArgumentError, ValueError),
        (LogicError, WorkflowError),
        (WorkflowRuntimeError, WorkflowError),
        (WorkflowRuntimeError, RuntimeError),
        (InvalidDefinitionError, LogicError),
        (TransitionError, LogicError),
        (NotEnabledTransitionError, TransitionError),
        (UndefinedTransitionError, TransitionError),
    ],
)
def test_an_error_is_caught_as_what_it_derives_from(
    error: type[Exception],
    base: type[Exception],
) -> None:
    assert issubclass(error, base)
