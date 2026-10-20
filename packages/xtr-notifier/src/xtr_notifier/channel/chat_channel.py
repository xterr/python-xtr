"""Sends notifications as chat messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_notifier.message import ChatMessage
from xtr_notifier.notification.chat_notification_interface import ChatNotificationInterface

from .abstract_channel import AbstractChannel

if TYPE_CHECKING:
    from xtr_notifier.notification import Notification
    from xtr_notifier.recipient import RecipientInterface

__all__ = ["ChatChannel"]


class ChatChannel(AbstractChannel):
    """Posts a notification to a chat — a Slack channel, a Telegram chat.

    The message is the one the notification renders with ``as_chat_message``
    when it implements
    :class:`~xtr_notifier.notification.ChatNotificationInterface`, else the
    subject with a summary of the notification for the provider to render.
    A chat message goes to a room, not a person, so every recipient is supported.
    """

    @override
    async def notify(
        self,
        notification: Notification,
        recipient: RecipientInterface,
        transport_name: str | None = None,
    ) -> None:
        """Post ``notification``, through ``transport_name`` when given."""
        message: ChatMessage | None = None
        if isinstance(notification, ChatNotificationInterface):
            message = notification.as_chat_message(recipient, transport_name)
        if message is None:
            message = ChatMessage.from_notification(notification)
        if transport_name is not None:
            message = message.with_transport(transport_name)
        await self._deliver(message)

    @override
    def supports(self, notification: Notification, recipient: RecipientInterface) -> bool:
        """Accept every notification and recipient."""
        return True
