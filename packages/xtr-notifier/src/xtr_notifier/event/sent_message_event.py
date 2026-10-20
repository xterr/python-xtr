"""A message a transport sent."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_notifier.message import SentMessage

__all__ = ["SentMessageEvent"]


@final
class SentMessageEvent(Event):
    """A transport sent a message, and the provider took it."""

    __slots__ = ("_message",)

    def __init__(self, message: SentMessage) -> None:
        """Describe the send ``message`` reports."""
        self._message = message

    @property
    def message(self) -> SentMessage:
        """What the transport reported about the send."""
        return self._message
