"""An event whose dispatch can end before every listener has run."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["StoppableEventInterface"]


@runtime_checkable
class StoppableEventInterface(Protocol):
    """An event a listener can mark as handled, so the listeners after it are skipped.

    A dispatcher asks before calling each listener, and stops at the first
    ``True``. How the event gets stopped is the event's business;
    :class:`~xtr_event_dispatcher_contracts.event.Event` offers
    :meth:`~xtr_event_dispatcher_contracts.event.Event.stop_propagation`.
    """

    def is_propagation_stopped(self) -> bool:
        """Tell whether the listeners still to run should be skipped."""
        ...
