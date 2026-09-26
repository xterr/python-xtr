"""Hand an event to whoever listens to it."""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

__all__ = ["EventDispatcherInterface"]

_EventT = TypeVar("_EventT")


@runtime_checkable
class EventDispatcherInterface(Protocol):
    """Announces that something happened, leaving who reacts to the application.

    The type code that emits events should depend on. It says nothing about
    how listeners are registered — that belongs to whoever builds the
    dispatcher — so a library announcing its lifecycle takes this and never
    learns what listens.
    """

    async def dispatch(self, event: _EventT, event_name: str | type | None = None) -> _EventT:
        """Run every listener of the event, highest priority first, and return the event.

        Listeners run one after the other, each awaited before the next. When
        the event is a
        :class:`~xtr_event_dispatcher_contracts.stoppable_event_interface.StoppableEventInterface`,
        no listener runs once it reports being stopped. An exception a listener
        raises reaches the caller unchanged, and the listeners after it do not
        run.

        Args:
            event: What happened, handed to every listener. Listeners may
                record their outcome on it, which is why it is returned.
            event_name: The name to dispatch under, or a class standing for
                its name (see
                :func:`~xtr_event_dispatcher_contracts.event_name_of.event_name_of`).
                ``None`` dispatches under the name of ``event``'s class.

        Returns:
            ``event`` itself.
        """
        ...
