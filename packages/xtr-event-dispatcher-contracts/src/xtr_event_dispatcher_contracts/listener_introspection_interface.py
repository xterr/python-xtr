"""Which listeners an event has, and in which order they run."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, overload, runtime_checkable

if TYPE_CHECKING:
    from .listener import Listener

__all__ = ["ListenerIntrospectionInterface"]


@runtime_checkable
class ListenerIntrospectionInterface(Protocol):
    """Reads the listeners of a dispatcher without registering any.

    For code that needs to know who listens — a debugging tool, a dispatcher
    wrapping another — but has no business adding or removing listeners.
    Wherever an event name is taken, a class stands for its name (see
    :func:`~xtr_event_dispatcher_contracts.event_name_of.event_name_of`).
    """

    @overload
    def get_listeners(self, event_name: None = None) -> dict[str, list[Listener]]: ...

    @overload
    def get_listeners(self, event_name: str | type) -> list[Listener]: ...

    def get_listeners(
        self,
        event_name: str | type | None = None,
    ) -> dict[str, list[Listener]] | list[Listener]:
        """Return the listeners of one event in the order they run, or of every event.

        Args:
            event_name: The event to read. ``None`` reads every event that has
                a listener, mapping each name to its listeners.
        """
        ...

    def get_listener_priority(self, event_name: str | type, listener: Listener) -> int | None:
        """Return the priority ``listener`` runs at for the event.

        Returns:
            The priority, or ``None`` when the event has no such listener.
        """
        ...

    def has_listeners(self, event_name: str | type | None = None) -> bool:
        """Tell whether the event — or, given ``None``, any event — has a listener."""
        ...
