"""The name of a workflow declared on a class, and how errors name that class."""

from __future__ import annotations

import re
from typing import Final

from xtr_workflow.exception import LogicError

__all__ = ["class_name", "workflow_name"]

_SUFFIX: Final = re.compile(r"(?<=.)(Workflow|StateMachine)$")
_ACRONYM_END: Final = re.compile(r"([A-Z]+)([A-Z][a-z])")
_WORD_START: Final = re.compile(r"([a-z\d])([A-Z])")


def workflow_name(name: str | None, class_: type) -> str:
    """Return ``name``, or the name derived from ``class_`` without one.

    The derived name is the class's name snake-cased, without its
    ``Workflow`` or ``StateMachine`` suffix: ``PullRequestStateMachine``
    gives ``pull_request``.

    Raises:
        LogicError: If ``name`` is empty: no event could be narrowed to it.
    """
    if name is None:
        stem = _SUFFIX.sub("", class_.__name__)
        return _WORD_START.sub(r"\1_\2", _ACRONYM_END.sub(r"\1_\2", stem)).lower()

    if not name:
        raise LogicError(
            f'The name of the workflow defined by "{class_name(class_)}" cannot be empty.'
        )

    return name


def class_name(class_: type) -> str:
    """Return ``class_`` as errors name it: its module, then its qualified name."""
    return f"{class_.__module__}.{class_.__qualname__}"
