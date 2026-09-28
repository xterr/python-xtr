"""The name an event is dispatched under, and listened to by."""

from __future__ import annotations

from typing import cast

__all__ = ["event_name_of"]


def event_name_of(event: str | type) -> str:
    """Return the event name ``event`` stands for.

    Events are keyed by name. A string is a name as it is; a class stands for
    its qualified name, ``"<module>.<qualname>"`` — the name an instance of it
    is dispatched under when no other is given. Every dispatcher normalises
    through this one function, so listening to ``OrderPlaced`` and to
    ``"shop.orders.OrderPlaced"`` is the same thing everywhere.

    Raises:
        TypeError: If ``event`` is neither — an event instance given where its
            class was meant, say.
    """
    if isinstance(event, str):
        return event
    given = cast("object", event)  # read as anything: a caller need not be type checked
    if not isinstance(given, type):
        message = f"an event name is a string or a class, got {given!r}"
        raise TypeError(message)

    return f"{event.__module__}.{event.__qualname__}"
