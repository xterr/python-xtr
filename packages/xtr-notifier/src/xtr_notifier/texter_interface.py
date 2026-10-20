"""What sends text and push messages directly, without a notification."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_notifier.message import MessageInterface, SentMessage

__all__ = ["TexterInterface"]


@runtime_checkable
class TexterInterface(Protocol):
    """Sends an SMS or a push message the application built itself — or queues it.

    Use it when the message, not a notification, is what the code has: a
    one-time code to a phone number, a push with provider options. A
    notification goes through the notifier instead, which picks the channels.
    """

    async def send(self, message: MessageInterface) -> SentMessage | None:
        """Send ``message`` now and report it, or queue it and return ``None``."""
        ...

    def supports(self, message: MessageInterface) -> bool:
        """Tell whether a configured transport sends ``message``."""
        ...
