"""Sends notifications as push messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_notifier.message import PushMessage
from xtr_notifier.notification.push_notification_interface import PushNotificationInterface

from .abstract_channel import AbstractChannel

if TYPE_CHECKING:
    from xtr_notifier.notification import Notification
    from xtr_notifier.recipient import RecipientInterface

__all__ = ["PushChannel"]


class PushChannel(AbstractChannel):
    """Pushes a notification — its subject as the title, its content as the body.

    The message is the one the notification renders with ``as_push_message``
    when it implements
    :class:`~xtr_notifier.notification.PushNotificationInterface`, else the
    default. Where it lands — a device, a topic — is the provider's options'
    business, so every recipient is supported.
    """

    @override
    async def notify(
        self,
        notification: Notification,
        recipient: RecipientInterface,
        transport_name: str | None = None,
    ) -> None:
        """Push ``notification``, through ``transport_name`` when given."""
        message: PushMessage | None = None
        if isinstance(notification, PushNotificationInterface):
            message = notification.as_push_message(recipient, transport_name)
        if message is None:
            message = PushMessage.from_notification(notification)
        if transport_name is not None:
            message = message.with_transport(transport_name)
        await self._deliver(message)

    @override
    def supports(self, notification: Notification, recipient: RecipientInterface) -> bool:
        """Accept every notification and recipient."""
        return True
