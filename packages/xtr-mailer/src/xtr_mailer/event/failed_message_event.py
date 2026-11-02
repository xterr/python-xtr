"""An email a transport failed to send."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_mime import RawMessage

__all__ = ["FailedMessageEvent"]


@final
class FailedMessageEvent(Event):
    """A transport failed to send an email.

    Dispatched before the error reaches the caller, so a listener can record the failure even
    when the caller — a failover transport — goes on to try another one.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_error", "_message")

    def __init__(self, message: RawMessage, error: Exception) -> None:
        """Describe ``message``, which failed with ``error``."""
        self._message: RawMessage = message
        self._error: Exception = error

    def get_message(self) -> RawMessage:
        """Return the email that was not sent."""
        return self._message

    def get_error(self) -> Exception:
        """Return why it was not sent."""
        return self._error
