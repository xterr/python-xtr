"""The bus side of the bundle: whether email is queued, and the bus it goes to.

Imported only when the messenger bundle is active. Importing it declares
:class:`~xtr_mailer.messenger.SendEmailMessage` to the bus, which is what lets a worker decode
a queued email.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_messenger import MessageBusConfig, MessageBusInterface, register_message, transports_of

from xtr_mailer.messenger import SendEmailMessage

from ._peers import MessageBusPeer

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["message_bus_peer", "routed"]

_WILDCARD = "*"

register_message(SendEmailMessage)


def message_bus_peer(message_bus: MessageBusInterface) -> MessageBusPeer:
    """Hold the application's message bus."""
    return MessageBusPeer(message_bus)


def routed(config: MessageBusConfig) -> bool:
    """Tell whether the bus does something with a queued email when it is dispatched.

    The routing is read as the bus reads it: an entry for the queued email's class or one of
    its bases, then the ``*`` catch-all, then the transports the class declares with
    ``register_message`` — each only when it names a transport. Any other key routes nothing
    on the bus, so it is passed over here too: a wire name, a class the email matches by its
    shape alone, a value that is no class at all. With ``handle_unrouted`` the email is
    handled in-process. An email routed nowhere would be dropped quietly by the bus, so it is
    sent at once instead: the mailer sends as it would without a bus until the application
    routes its email.
    """
    if config.handle_unrouted:
        return True
    keys = (*SendEmailMessage.__mro__, _WILDCARD)
    return any(_names_a_transport(config.routing.get(key, ())) for key in keys) or bool(
        transports_of(SendEmailMessage)
    )


def _names_a_transport(route: str | Sequence[str]) -> bool:
    """Tell whether ``route`` names a transport: one name, or a list of at least one."""
    return isinstance(route, str) or len(route) > 0
