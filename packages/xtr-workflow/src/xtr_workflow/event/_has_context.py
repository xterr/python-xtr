"""The context an event carries from the call that moved the subject."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .event import Event

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_workflow.marking import Marking
    from xtr_workflow.transition import Transition
    from xtr_workflow.workflow_interface import WorkflowInterface

__all__ = ["HasContextTrait"]


class HasContextTrait(Event):
    """An event that also carries the context of the call that moved the subject.

    What every event but the guard event derives from: a guard decides
    whether a transition may run before any call's context is in play.
    """

    def __init__(
        self,
        subject: object,
        marking: Marking,
        transition: Transition | None = None,
        workflow: WorkflowInterface | None = None,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Announce a step of ``workflow`` moving ``subject``, with the call's ``context``.

        Args:
            subject: The object being moved.
            marking: Where it is at this step.
            transition: The transition being applied; ``None`` when the
                subject is given its initial marking.
            workflow: The workflow moving it.
            context: The context the call that moved it was given.
        """
        super().__init__(subject, marking, transition, workflow)
        self._context: dict[str, object] = dict(context) if context is not None else {}

    def get_context(self) -> dict[str, object]:
        """Return the context of the call that moved the subject; a copy."""
        return dict(self._context)
