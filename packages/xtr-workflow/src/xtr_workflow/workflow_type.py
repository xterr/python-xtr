"""Whether a subject is in one place at a time, or in several."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["WorkflowType"]


class WorkflowType(StrEnum):
    """Whether a definition runs as a state machine or as a workflow.

    A string enum: each member is the string configuration names its type
    by, so the two compare equal with no conversion step.
    """

    STATE_MACHINE = "state_machine"
    """The subject is in one place, and only one, at any time."""

    WORKFLOW = "workflow"
    """The subject can be in several places at the same time."""
