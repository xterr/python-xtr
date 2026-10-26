"""What the notifier's services take from optional peers, present or not.

A peer bundle may be inactive — no HTTP client installed, no event
dispatcher, no message bus — and a container cannot inject what it does not
hold. So each peer reaches the services through a holder the bundle always
registers: built from the peer's service when the peer is active, holding
``None`` otherwise. The services then take one fixed set of parameters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_messenger import MessageBusInterface

__all__ = ["EventDispatcherPeer", "HttpClientPeer", "MessageBusPeer"]


@final
class HttpClientPeer:
    """The HTTP client providers are reached through, or ``None`` without one."""

    __slots__: ClassVar[tuple[str, ...]] = ("http_client",)

    def __init__(self, http_client: HttpClientInterface | None) -> None:
        """Hold ``http_client``."""
        self.http_client: HttpClientInterface | None = http_client


@final
class EventDispatcherPeer:
    """Where messages are announced, or ``None`` without an event dispatcher."""

    __slots__: ClassVar[tuple[str, ...]] = ("event_dispatcher",)

    def __init__(self, event_dispatcher: EventDispatcherInterface | None) -> None:
        """Hold ``event_dispatcher``."""
        self.event_dispatcher: EventDispatcherInterface | None = event_dispatcher


@final
class MessageBusPeer:
    """The bus a kind of message is queued on, or ``None`` to send it at once."""

    __slots__: ClassVar[tuple[str, ...]] = ("message_bus",)

    def __init__(self, message_bus: MessageBusInterface | None) -> None:
        """Hold ``message_bus``."""
        self.message_bus: MessageBusInterface | None = message_bus
