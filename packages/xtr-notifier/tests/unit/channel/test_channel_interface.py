from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_notifier.channel import ChannelInterface

if TYPE_CHECKING:
    from xtr_notifier.notification import Notification
    from xtr_notifier.recipient import RecipientInterface


class _Channel:
    async def notify(
        self,
        notification: Notification,
        recipient: RecipientInterface,
        transport_name: str | None = None,
    ) -> None:
        del notification, recipient, transport_name

    def supports(self, notification: Notification, recipient: RecipientInterface) -> bool:
        return bool(notification.subject) and recipient is not None


def test_anything_that_notifies_and_says_what_it_supports_is_a_channel() -> None:
    assert isinstance(_Channel(), ChannelInterface)
    assert not isinstance(object(), ChannelInterface)
