from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_notifier import NotifierInterface

if TYPE_CHECKING:
    from xtr_notifier.notification import Notification
    from xtr_notifier.recipient import RecipientInterface


class _Structural:
    async def send(self, notification: Notification, *recipients: RecipientInterface) -> None:
        del notification, recipients


def test_anything_that_sends_a_notification_is_a_notifier() -> None:
    assert isinstance(_Structural(), NotifierInterface)
    assert not isinstance(object(), NotifierInterface)
