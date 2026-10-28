"""A value handed to a workflow cannot be used."""

from __future__ import annotations

from .workflow_error import WorkflowError

__all__ = ["InvalidArgumentError"]


class InvalidArgumentError(WorkflowError, ValueError):
    """A value handed to a workflow, or to one of its parts, cannot be used.

    An arc's weight below 1, a number of tokens a place cannot give: each is
    refused where it is handed over, before it changes anything.
    """
