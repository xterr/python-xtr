"""Sends notifications as text messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_notifier.exception import LogicError
from xtr_notifier.message import SmsMessage
from xtr_notifier.notification.sms_notification_interface import SmsNotificationInterface
from xtr_notifier.recipient import SmsRecipientInterface

from .abstract_channel import AbstractChannel

if TYPE_CHECKING:
    from xtr_notifier.notification import Notification
    from xtr_notifier.recipient import RecipientInterface

__all__ = ["SmsChannel"]


class SmsChannel(AbstractChannel):
    """Texts a notification to a recipient's phone number.

    The message is the one the notification renders with ``as_sms_message``
    when it implements
    :class:`~xtr_notifier.notification.SmsNotificationInterface`, else the
    subject. Only a recipient with a phone number is supported.
    """

    @override
    async def notify(
        self,
        notification: Notification,
        recipient: RecipientInterface,
        transport_name: str | None = None,
    ) -> None:
        """Text ``notification`` to ``recipient``, through ``transport_name`` when given.

        Raises:
            LogicError: If ``recipient`` has no phone number.
        """
        if not (isinstance(recipient, SmsRecipientInterface) and recipient.phone):
            raise LogicError(f'"{type(self).__name__}" needs a recipient with a phone number.')
        message: SmsMessage | None = None
        if isinstance(notification, SmsNotificationInterface):
            message = notification.as_sms_message(recipient, transport_name)
        if message is None:
            message = SmsMessage.from_notification(notification, recipient)
        if transport_name is not None:
            message = message.with_transport(transport_name)
        await self._deliver(message)

    @override
    def supports(self, notification: Notification, recipient: RecipientInterface) -> bool:
        """Accept a recipient with a phone number."""
        return isinstance(recipient, SmsRecipientInterface) and bool(recipient.phone)
