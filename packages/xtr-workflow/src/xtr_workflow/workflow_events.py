"""The names the workflow events are dispatched under."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final, final

from .event import (
    AnnounceEvent,
    CompletedEvent,
    EnteredEvent,
    EnterEvent,
    GuardEvent,
    LeaveEvent,
    TransitionEvent,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .event import Event

__all__ = ["WorkflowEvents"]


@final
class WorkflowEvents:
    """The name every workflow event goes out under for every workflow, in the order they come.

    A workflow dispatches each event under this name, then narrowed to its
    own name and to a place or transition (``get_name`` on each event class
    builds those). :attr:`ALIASES` lets a listener declare the event class
    instead of the name.
    """

    GUARD: Final[str] = "workflow.guard"
    """Listeners may block a transition; carries a :class:`GuardEvent`."""

    LEAVE: Final[str] = "workflow.leave"
    """The subject is leaving a place; carries a :class:`LeaveEvent`."""

    TRANSITION: Final[str] = "workflow.transition"
    """A transition is being applied; carries a :class:`TransitionEvent`."""

    ENTER: Final[str] = "workflow.enter"
    """The subject is entering a place; carries an :class:`EnterEvent`."""

    ENTERED: Final[str] = "workflow.entered"
    """The subject has entered a place; carries an :class:`EnteredEvent`."""

    COMPLETED: Final[str] = "workflow.completed"
    """A transition has been applied; carries a :class:`CompletedEvent`."""

    ANNOUNCE: Final[str] = "workflow.announce"
    """A transition is enabled after the move; carries an :class:`AnnounceEvent`."""

    ALIASES: Final[Mapping[type[Event], str]] = MappingProxyType(
        {
            GuardEvent: GUARD,
            LeaveEvent: LEAVE,
            TransitionEvent: TRANSITION,
            EnterEvent: ENTER,
            EnteredEvent: ENTERED,
            CompletedEvent: COMPLETED,
            AnnounceEvent: ANNOUNCE,
        }
    )
    """Each event class, mapped to the name it is dispatched under for every workflow."""
