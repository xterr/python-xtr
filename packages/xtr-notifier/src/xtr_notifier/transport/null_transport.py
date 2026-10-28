"""A transport that sends nothing anywhere."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_notifier.event import MessageEvent, SentMessageEvent
from xtr_notifier.message import NullMessage, SentMessage

from .transport_interface import TransportInterface

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface

    from xtr_notifier.message import MessageInterface

__all__ = ["NullTransport"]


@final
class NullTransport(TransportInterface):
    """Accepts every message and sends it nowhere: ``null://null``.

    For an environment that must not reach a provider — a test run, a local
    machine — while everything up to the send still happens, events included,
    so a listener sees what would have gone out. Talks to no provider, so it
    takes no HTTP client.
    """

    __slots__ = ("_event_dispatcher",)

    def __init__(self, event_dispatcher: EventDispatcherInterface | None = None) -> None:
        """Announce each message on ``event_dispatcher``; ``None`` announces nothing."""
        self._event_dispatcher = event_dispatcher

    @override
    async def send(self, message: MessageInterface) -> SentMessage:
        """Report ``message`` as sent, wrapped in a :class:`NullMessage`."""
        null_message = NullMessage(message)
        sent = SentMessage(null_message, str(self))
        if self._event_dispatcher is not None:
            _ = await self._event_dispatcher.dispatch(MessageEvent(null_message))
            _ = await self._event_dispatcher.dispatch(SentMessageEvent(sent))
        return sent

    @override
    def supports(self, message: MessageInterface) -> bool:
        """Accept every message."""
        return True

    @override
    def __str__(self) -> str:
        """Name it ``null``."""
        return "null"
