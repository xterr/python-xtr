"""The bus side of the bundle: whether email is queued, and the bus it goes to.

Imported only when the messenger bundle is active. Importing it declares
:class:`~xtr_mailer.messenger.SendEmailMessage` to the bus, which is what lets a worker decode
a queued email.
"""

from __future__ import annotations

from xtr_messenger import MessageBusConfig, MessageBusInterface, name_of, register_message

from xtr_mailer.messenger import SendEmailMessage

from ._peers import MessageBusPeer

__all__ = ["message_bus_peer", "routed"]

_WILDCARD = "*"

register_message(SendEmailMessage)


def message_bus_peer(message_bus: MessageBusInterface) -> MessageBusPeer:
    """Hold the application's message bus."""
    return MessageBusPeer(message_bus)


def routed(config: MessageBusConfig) -> bool:
    """Tell whether the bus does something with a queued email when it is dispatched.

    An email the routing names — by its class, its wire name or the ``*`` catch-all — goes to
    a transport; with ``handle_unrouted`` it is handled in-process. Anything else would be
    dropped quietly by the bus, so it is sent at once instead: the mailer sends as it would
    without a bus until the application routes its email.
    """
    if config.handle_unrouted:
        return True
    names = {_WILDCARD, name_of(SendEmailMessage)}
    return any(
        key in names if isinstance(key, str) else issubclass(SendEmailMessage, key)
        for key in config.routing
    )
