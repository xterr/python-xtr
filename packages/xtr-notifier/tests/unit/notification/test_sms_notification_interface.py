from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_notifier.message import SmsMessage
from xtr_notifier.notification import Notification
from xtr_notifier.notification.sms_notification_interface import SmsNotificationInterface

if TYPE_CHECKING:
    from xtr_notifier.recipient import SmsRecipientInterface


class _Rendering(Notification):
    def as_sms_message(
        self, recipient: SmsRecipientInterface, transport_name: str | None
    ) -> SmsMessage | None:
        return SmsMessage(recipient.phone, "hi", transport=transport_name)


def test_a_notification_rendering_its_own_sms_message_is_a_sms_notification() -> None:
    assert isinstance(_Rendering(), SmsNotificationInterface)
    assert not isinstance(Notification(), SmsNotificationInterface)
