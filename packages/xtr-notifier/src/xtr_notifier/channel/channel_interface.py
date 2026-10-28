"""What turns a notification into a message and sends it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_notifier.notification import Notification
    from xtr_notifier.recipient import RecipientInterface

__all__ = ["ChannelInterface"]


@runtime_checkable
class ChannelInterface(Protocol):
    """A way a notification reaches a recipient — chat, SMS, push.

    The notifier asks :meth:`supports` before :meth:`notify`, so a channel
    refuses a recipient it cannot reach — a text message to someone without a
    phone number — before anything is sent.
    """

    async def notify(
        self,
        notification: Notification,
        recipient: RecipientInterface,
        transport_name: str | None = None,
    ) -> None:
        """Send ``notification`` to ``recipient``.

        Args:
            notification: What to say.
            recipient: Who to say it to.
            transport_name: The transport to send through (``"slack"`` in
                ``"chat/slack"``), or ``None`` for the first that supports it.
        """
        ...

    def supports(self, notification: Notification, recipient: RecipientInterface) -> bool:
        """Tell whether this channel can send ``notification`` to ``recipient``."""
        ...
