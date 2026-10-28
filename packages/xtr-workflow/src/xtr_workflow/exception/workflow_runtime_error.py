"""Something a workflow depends on failed while it ran."""

from __future__ import annotations

from .workflow_error import WorkflowError

__all__ = ["WorkflowRuntimeError"]


class WorkflowRuntimeError(WorkflowError, RuntimeError):
    """Something a workflow depends on failed while it ran, rather than how it was used."""
