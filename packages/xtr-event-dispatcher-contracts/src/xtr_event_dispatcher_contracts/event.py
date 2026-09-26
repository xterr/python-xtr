"""The base class of an event, carrying data or not."""

from __future__ import annotations

__all__ = ["Event"]


class Event:
    """An event any listener can stop, so the listeners after it are skipped.

    Carries no data itself: derive from it and add what the listeners need,
    usually as a dataclass. It satisfies
    :class:`~xtr_event_dispatcher_contracts.stoppable_event_interface.StoppableEventInterface`
    without deriving from it, so a class of events stays a plain class.

    ```python
    @dataclass(frozen=True)
    class OrderPlaced(Event):
        order_id: int


    def reject_fraud(event: OrderPlaced) -> None:
        if is_fraudulent(event.order_id):
            event.stop_propagation()
    ```
    """

    # A class-level default rather than one set in ``__init__``: a dataclass
    # deriving from this never calls it, and an event nobody stopped needs no
    # state of its own.
    _propagation_stopped: bool = False

    def is_propagation_stopped(self) -> bool:
        """Tell whether a listener has stopped this event."""
        return self._propagation_stopped

    def stop_propagation(self) -> None:
        """Skip every listener that has not run yet for this event.

        Works on a frozen dataclass too: stopping is about the dispatch, not
        a change to the data the event carries.
        """
        object.__setattr__(self, "_propagation_stopped", True)
