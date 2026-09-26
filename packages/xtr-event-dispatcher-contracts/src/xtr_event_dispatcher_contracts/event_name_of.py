"""The name an event is dispatched under, and listened to by."""

from __future__ import annotations

__all__ = ["event_name_of"]


def event_name_of(event: str | type) -> str:
    """Return the event name ``event`` stands for.

    Events are keyed by name. A string is a name as it is; a class stands for
    its qualified name, ``"<module>.<qualname>"`` — the name an instance of it
    is dispatched under when no other is given. Every dispatcher normalises
    through this one function, so listening to ``OrderPlaced`` and to
    ``"shop.orders.OrderPlaced"`` is the same thing everywhere.
    """
    if isinstance(event, str):
        return event

    return f"{event.__module__}.{event.__qualname__}"
