"""Logging every place a subject leaves and enters, and every transition it takes."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_logging_contracts import LoggerInterface

from xtr_workflow.event import Event
from xtr_workflow.exception import LogicError
from xtr_workflow.workflow_events import WorkflowEvents

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents

    from xtr_workflow.transition import Transition

__all__ = ["AuditTrailListener"]


@final
class AuditTrailListener(EventSubscriberInterface):
    """Logs each move of a subject: the places it leaves, the transition, the places it enters.

    One info line per place a transition takes the subject out of, one for the
    transition, then one per place it puts the subject in — each naming the
    subject's class and the workflow — so the log tells where every subject has
    been, in order.
    """

    __slots__: tuple[str, ...] = ("_logger",)

    def __init__(self, logger: LoggerInterface) -> None:
        """Write the audit trail to ``logger``."""
        self._logger = logger

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        return {
            WorkflowEvents.LEAVE: ["on_leave"],
            WorkflowEvents.TRANSITION: ["on_transition"],
            WorkflowEvents.ENTER: ["on_enter"],
        }

    def on_leave(self, event: Event) -> None:
        """Log each place the transition takes the subject out of.

        Raises:
            LogicError: If the event carries no transition, or no workflow.
        """
        for arc in _transition_of(event).get_froms(as_arc=True):
            self._logger.info(_line("Leaving", arc.place, event))

    def on_transition(self, event: Event) -> None:
        """Log the transition the subject is taking.

        Raises:
            LogicError: If the event carries no transition, or no workflow.
        """
        self._logger.info(_line("Transition", _transition_of(event).get_name(), event))

    def on_enter(self, event: Event) -> None:
        """Log each place the transition puts the subject in.

        Raises:
            LogicError: If the event carries no transition, or no workflow.
        """
        for arc in _transition_of(event).get_tos(as_arc=True):
            self._logger.info(_line("Entering", arc.place, event))


def _transition_of(event: Event) -> Transition:
    """Return the transition the subject is taking.

    Raises:
        LogicError: If the event carries none. A workflow sends an event
            without a transition only for a subject's initial marking, which
            the trail does not listen to; this one was built by hand.
    """
    transition = event.get_transition()
    if transition is None:
        raise LogicError(f'The "{type(event).__name__}" event carries no transition.')
    return transition


def _line(step: str, node: str, event: Event) -> str:
    """Return one line of the trail: the step, the place or transition, the subject, the workflow.

    Every line reads ``<step> "<node>" for subject of class "<class>" in
    workflow "<workflow>".``, the class named by its module, then its
    qualified name. The text is finished here: the trail passes the logger no
    context to fill it from.

    Raises:
        LogicError: If the event carries no workflow.
    """
    subject_class = type(event.get_subject())
    return (
        f'{step} "{node}" for subject of class '
        f'"{subject_class.__module__}.{subject_class.__qualname__}" '
        f'in workflow "{event.get_workflow_name()}".'
    )
