"""A workflow was used in a way that cannot work."""

from __future__ import annotations

from .workflow_error import WorkflowError

__all__ = ["LogicError"]


class LogicError(WorkflowError):
    """A workflow was used in a way that cannot work.

    A transition applied where none of that name exists or none is enabled, a
    definition its type cannot run: each is a mistake in how the workflow is
    defined or called, not a failure of something it depends on.
    """
