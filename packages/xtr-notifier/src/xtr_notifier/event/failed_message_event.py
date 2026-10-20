"""A message a transport failed to send."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_notifier.message import MessageInterface

__all__ = ["FailedMessageEvent"]


@final
class FailedMessageEvent(Event):
    """A transport failed to send a message.

    Dispatched before the error reaches the caller, so a listener can record
    the failure even when the caller — a failover transport — goes on to try
    another provider.
    """

    __slots__ = ("_error", "_message")

    def __init__(self, message: MessageInterface, error: Exception) -> None:
        """Describe ``message``, which failed with ``error``."""
        self._message = message
        self._error = error

    @property
    def message(self) -> MessageInterface:
        """The message that was not sent."""
        return self._message

    @property
    def error(self) -> Exception:
        """Why it was not sent."""
        return self._error
