"""Telling whether a workflow moves a subject."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_workflow.workflow_interface import WorkflowInterface

__all__ = ["WorkflowSupportStrategyInterface"]


@runtime_checkable
class WorkflowSupportStrategyInterface(Protocol):
    """Tells whether a workflow moves a subject.

    A workflow takes any object; which objects it is meant for is the
    application's to say, and a registry asks the strategy each workflow was
    added with to find the workflow of a subject.

    Deciding reads the workflow and the subject alone, without asking a
    listener, so it is not a coroutine: a workflow is looked up wherever a
    subject is at hand.
    """

    def supports(self, workflow: WorkflowInterface, subject: object) -> bool:
        """Tell whether ``workflow`` moves ``subject``."""
        ...
