from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_notifier.message import ChatMessage
from xtr_notifier.notification import Notification
from xtr_notifier.notification.chat_notification_interface import ChatNotificationInterface

if TYPE_CHECKING:
    from xtr_notifier.recipient import RecipientInterface


class _Rendering(Notification):
    def as_chat_message(
        self, recipient: RecipientInterface, transport_name: str | None
    ) -> ChatMessage | None:
        return ChatMessage(type(recipient).__name__, transport=transport_name)


def test_a_notification_rendering_its_own_chat_message_is_a_chat_notification() -> None:
    assert isinstance(_Rendering(), ChatNotificationInterface)
    assert not isinstance(Notification(), ChatNotificationInterface)
