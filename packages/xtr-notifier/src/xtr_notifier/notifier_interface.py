"""What sends a notification."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_notifier.notification import Notification
    from xtr_notifier.recipient import RecipientInterface

__all__ = ["NotifierInterface"]


@runtime_checkable
class NotifierInterface(Protocol):
    """Sends a notification to its recipients, on the channels it calls for."""

    async def send(self, notification: Notification, *recipients: RecipientInterface) -> None:
        """Send ``notification`` to each of ``recipients`` — to nobody in particular when none.

        Implementations raise :class:`~xtr_notifier.exception.LogicError` when a
        channel cannot be determined, does not exist, or cannot reach a recipient.
        """
        ...
