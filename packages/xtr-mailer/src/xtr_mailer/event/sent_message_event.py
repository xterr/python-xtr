"""An email a transport sent."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_mailer.sent_message import SentMessage

__all__ = ["SentMessageEvent"]


@final
class SentMessageEvent(Event):
    """A transport sent an email, and the server or the provider took it."""

    __slots__: ClassVar[tuple[str, ...]] = ("_message",)

    def __init__(self, message: SentMessage) -> None:
        """Describe the send ``message`` reports."""
        self._message: SentMessage = message

    def get_message(self) -> SentMessage:
        """Return what the transport sent, and the message id it learned."""
        return self._message
