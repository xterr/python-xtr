"""A message about to be sent, or queued to be."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_notifier.message import MessageInterface

__all__ = ["MessageEvent"]


@final
class MessageEvent(Event):
    """A message is about to be sent — or was handed to a message bus to be sent later.

    Dispatched by a transport before it sends, and by a chatter or a texter
    when it queues instead, so a listener sees every message once whichever
    way it leaves.
    """

    __slots__ = ("_message", "_queued")

    def __init__(self, message: MessageInterface, queued: bool = False) -> None:
        """Describe ``message``, and whether it was queued rather than sent now."""
        self._message = message
        self._queued = queued

    @property
    def message(self) -> MessageInterface:
        """The message."""
        return self._message

    @property
    def queued(self) -> bool:
        """Whether the message was handed to a message bus instead of sent now."""
        return self._queued
