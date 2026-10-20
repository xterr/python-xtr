"""What sends chat messages directly, without a notification."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_notifier.message import MessageInterface, SentMessage

__all__ = ["ChatterInterface"]


@runtime_checkable
class ChatterInterface(Protocol):
    """Sends a chat message the application built itself — or queues it for later.

    Use it when the message, not a notification, is what the code has: a reply
    in a thread, a message with provider options. A notification goes through
    the notifier instead, which picks the channels.
    """

    async def send(self, message: MessageInterface) -> SentMessage | None:
        """Send ``message`` now and report it, or queue it and return ``None``."""
        ...

    def supports(self, message: MessageInterface) -> bool:
        """Tell whether a configured transport sends ``message``."""
        ...
