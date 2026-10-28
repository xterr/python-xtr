"""The error every other error of this package derives from."""

from __future__ import annotations

__all__ = ["WorkflowError"]


class WorkflowError(Exception):
    """Something a workflow could not do — catch this to catch them all."""
