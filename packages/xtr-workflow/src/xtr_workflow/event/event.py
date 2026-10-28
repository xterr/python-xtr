"""What every workflow event carries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_event_dispatcher_contracts import Event as BaseEvent

from xtr_workflow.exception import LogicError

if TYPE_CHECKING:
    from xtr_workflow.marking import Marking
    from xtr_workflow.transition import Transition
    from xtr_workflow.workflow_interface import WorkflowInterface

__all__ = ["Event"]


class Event(BaseEvent):
    """The subject a workflow is moving, its marking, the transition and the workflow.

    A plain mutable class rather than a dataclass: the guard event collects
    blockers and the transition event may have its context replaced, both by
    the listeners it is handed to.
    """

    def __init__(
        self,
        subject: object,
        marking: Marking,
        transition: Transition | None = None,
        workflow: WorkflowInterface | None = None,
    ) -> None:
        """Announce a step of ``workflow`` moving ``subject`` through ``transition``.

        Args:
            subject: The object being moved.
            marking: Where it is at this step.
            transition: The transition being applied; ``None`` when the
                subject is given its initial marking.
            workflow: The workflow moving it.
        """
        self._subject: object = subject
        self._marking: Marking = marking
        self._transition: Transition | None = transition
        self._workflow: WorkflowInterface | None = workflow

    def get_marking(self) -> Marking:
        """Return where the subject is at this step."""
        return self._marking

    def get_subject(self) -> object:
        """Return the object being moved."""
        return self._subject

    def get_transition(self) -> Transition | None:
        """Return the transition being applied; ``None`` for the initial marking."""
        return self._transition

    def get_workflow_name(self) -> str:
        """Return the name of the workflow moving the subject.

        Raises:
            LogicError: If the event was built without a workflow.
        """
        return self._required_workflow().get_name()

    def get_metadata(self, key: str, subject: str | Transition | None) -> object | None:
        """Return one entry of the metadata of the workflow, of a place or of a transition.

        Args:
            key: The name of the entry.
            subject: ``None`` for the workflow, a place name for that place, or
                a transition for that transition.

        Raises:
            LogicError: If the event was built without a workflow.
        """
        return self._required_workflow().get_metadata_store().get_metadata(key, subject)

    def _required_workflow(self) -> WorkflowInterface:
        """Return the workflow, which reading its name or metadata needs.

        Raises:
            LogicError: If the event was built without one.
        """
        if self._workflow is None:
            raise LogicError(f'The "{type(self).__name__}" event carries no workflow.')
        return self._workflow
