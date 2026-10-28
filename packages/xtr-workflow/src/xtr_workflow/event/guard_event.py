"""Asking listeners whether a transition may be applied."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

from xtr_workflow.transition_blocker import TransitionBlocker
from xtr_workflow.transition_blocker_list import TransitionBlockerList

from ._event_name import event_name
from .event import Event

if TYPE_CHECKING:
    from xtr_workflow.marking import Marking
    from xtr_workflow.transition import Transition
    from xtr_workflow.workflow_interface import WorkflowInterface

__all__ = ["GuardEvent"]


@final
class GuardEvent(Event):
    """Asks listeners whether a transition may be applied, collecting why not.

    Dispatched for every transition the marking enables, before it is
    applied or reported enabled; any blocker a listener adds keeps it from
    running, and is what the caller is told.
    """

    def __init__(
        self,
        subject: object,
        marking: Marking,
        transition: Transition,
        workflow: WorkflowInterface | None = None,
    ) -> None:
        """Ask whether ``transition`` may move ``subject`` out of ``marking``."""
        super().__init__(subject, marking, transition, workflow)
        self._transition_blocker_list: TransitionBlockerList = TransitionBlockerList()

    @staticmethod
    def get_name(workflow_name: str | None = None, node: str | None = None) -> str:
        """Return the name this event goes out under, narrowed to a workflow and a transition.

        Raises:
            InvalidArgumentError: If a transition is named without its workflow.
        """
        return event_name(GuardEvent, workflow_name, node)

    @override
    def get_transition(self) -> Transition:
        """Return the transition being guarded."""
        # Never None: the constructor requires it.
        return cast("Transition", super().get_transition())

    def is_blocked(self) -> bool:
        """Tell whether a listener blocked the transition."""
        return not self._transition_blocker_list.is_empty()

    def set_blocked(self, blocked: bool, message: str | None = None) -> None:
        """Block the transition, or lift every blocker added so far.

        Args:
            blocked: Block it, or unblock it.
            message: Why it is blocked; without one, the reason names the
                class of the listener that blocked it.
        """
        if not blocked:
            self._transition_blocker_list.clear()
            return

        self._transition_blocker_list.add(TransitionBlocker.create_unknown(message))

    def get_transition_blocker_list(self) -> TransitionBlockerList:
        """Return every reason given so far for blocking the transition."""
        return self._transition_blocker_list

    def add_transition_blocker(self, transition_blocker: TransitionBlocker) -> None:
        """Block the transition for the reason ``transition_blocker`` gives."""
        self._transition_blocker_list.add(transition_blocker)
