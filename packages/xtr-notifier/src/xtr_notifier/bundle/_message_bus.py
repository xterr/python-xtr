"""The bus side of the bundle: which messages are queued, and the bus they go to.

Imported only when the messenger bundle is active.
"""

from __future__ import annotations

from xtr_messenger import MessageBusConfig, MessageBusInterface

from xtr_notifier.messenger import MESSAGE_NAMES

from ._peers import MessageBusPeer

__all__ = ["message_bus_peer", "routed"]

_WILDCARD = "*"


def message_bus_peer(message_bus: MessageBusInterface) -> MessageBusPeer:
    """Hold the application's message bus."""
    return MessageBusPeer(message_bus)


def routed(config: MessageBusConfig, message_type: type) -> bool:
    """Tell whether the bus does something with ``message_type`` when it is dispatched.

    A message the routing names — by its class, its wire name or the ``*``
    catch-all — goes to a transport; with ``handle_unrouted`` any message is
    handled in-process. Anything else would be dropped quietly by the bus, so
    it is sent at once instead: the behaviour stays the same until the
    application routes the message.
    """
    if config.handle_unrouted:
        return True
    names = {_WILDCARD, MESSAGE_NAMES[message_type]}
    return any(
        key in names if isinstance(key, str) else issubclass(message_type, key)
        for key in config.routing
    )
