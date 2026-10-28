"""Every error this package defines, each deriving from :class:`WorkflowError`."""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError
from .invalid_definition_error import InvalidDefinitionError
from .logic_error import LogicError
from .not_enabled_transition_error import NotEnabledTransitionError
from .transition_error import TransitionError
from .undefined_transition_error import UndefinedTransitionError
from .workflow_error import WorkflowError
from .workflow_runtime_error import WorkflowRuntimeError

__all__ = [
    "InvalidArgumentError",
    "InvalidDefinitionError",
    "LogicError",
    "NotEnabledTransitionError",
    "TransitionError",
    "UndefinedTransitionError",
    "WorkflowError",
    "WorkflowRuntimeError",
]
