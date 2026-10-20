from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_notifier.message import PushMessage
from xtr_notifier.notification import Notification
from xtr_notifier.notification.push_notification_interface import PushNotificationInterface

if TYPE_CHECKING:
    from xtr_notifier.recipient import RecipientInterface


class _Rendering(Notification):
    def as_push_message(
        self, recipient: RecipientInterface, transport_name: str | None
    ) -> PushMessage | None:
        return PushMessage(type(recipient).__name__, "there", transport=transport_name)


def test_a_notification_rendering_its_own_push_message_is_a_push_notification() -> None:
    assert isinstance(_Rendering(), PushNotificationInterface)
    assert not isinstance(Notification(), PushNotificationInterface)
