from __future__ import annotations

from typing import TYPE_CHECKING, override

import pytest
from xtr_messenger import Envelope, HandlersFailedError
from xtr_messenger.event import WorkerMessageFailedEvent

from xtr_notifier import AdminRecipientsProviderInterface, NotifierInterface
from xtr_notifier.event_listener.send_failed_message_to_notifier_listener import (
    SendFailedMessageToNotifierListener,
)
from xtr_notifier.message import ChatMessage, PushMessage, SmsMessage
from xtr_notifier.notification import Importance
from xtr_notifier.recipient import Recipient

if TYPE_CHECKING:
    from xtr_notifier.notification import Notification
    from xtr_notifier.recipient import RecipientInterface

pytestmark = pytest.mark.anyio


class _OrderPlaced:
    pass


class _Notifier(NotifierInterface):
    def __init__(self) -> None:
        self.sent: list[tuple[Notification, tuple[RecipientInterface, ...]]] = []

    @override
    async def send(self, notification: Notification, *recipients: RecipientInterface) -> None:
        self.sent.append((notification, recipients))


class _NotifierWithAdmins(_Notifier, AdminRecipientsProviderInterface):
    def __init__(self, *admins: RecipientInterface) -> None:
        super().__init__()
        self._admins: tuple[RecipientInterface, ...] = admins

    @property
    @override
    def admin_recipients(self) -> tuple[RecipientInterface, ...]:
        return self._admins


def _event(
    error: Exception, *, will_retry: bool = False, message: object | None = None
) -> WorkerMessageFailedEvent:
    return WorkerMessageFailedEvent(
        Envelope(_OrderPlaced() if message is None else message),
        "receiver",
        error,
        will_retry=will_retry,
    )


async def test_it_reports_the_failure_with_high_importance_to_nobody_without_admins() -> None:
    notifier = _Notifier()

    await SendFailedMessageToNotifierListener(notifier).on_message_failed(
        _event(RuntimeError("Boom"))
    )

    [(notification, recipients)] = notifier.sent
    assert notification.subject == 'A "_OrderPlaced" message has just failed: RuntimeError: Boom.'
    assert notification.importance is Importance.HIGH
    # No traceback by default: it may hold the failed message's own data.
    assert notification.exception is None
    assert notification.exception_as_string == ""
    assert recipients == ()


async def test_the_traceback_is_attached_when_asked_for() -> None:
    notifier = _Notifier()

    await SendFailedMessageToNotifierListener(notifier, include_traceback=True).on_message_failed(
        _event(RuntimeError("Boom"))
    )

    assert notifier.sent[0][0].exception_as_string.endswith("RuntimeError: Boom")


@pytest.mark.parametrize(
    "message",
    [ChatMessage("down"), SmsMessage("+40700000000", "down"), PushMessage("down", "body")],
    ids=["chat", "sms", "push"],
)
async def test_a_failed_notification_does_not_notify_again(message: object) -> None:
    # Reporting it would send another notification through the transport that just failed.
    notifier = _Notifier()

    await SendFailedMessageToNotifierListener(notifier).on_message_failed(
        _event(RuntimeError("Boom"), message=message)
    )

    assert notifier.sent == []


async def test_it_reports_the_failure_to_the_admin_recipients() -> None:
    admin = Recipient("admin@example.com")
    notifier = _NotifierWithAdmins(admin)

    await SendFailedMessageToNotifierListener(notifier).on_message_failed(
        _event(RuntimeError("Boom"))
    )

    assert notifier.sent[0][1] == (admin,)


async def test_it_reports_nothing_when_the_message_will_be_retried() -> None:
    notifier = _Notifier()

    await SendFailedMessageToNotifierListener(notifier).on_message_failed(
        _event(RuntimeError("Boom"), will_retry=True)
    )

    assert notifier.sent == []


async def test_it_reports_what_the_first_failed_handler_raised() -> None:
    notifier = _Notifier()
    first = ValueError("bad total")
    handlers_failed = HandlersFailedError(
        Envelope(_OrderPlaced()), {"bill": first, "ship": RuntimeError("later")}
    )

    await SendFailedMessageToNotifierListener(notifier, include_traceback=True).on_message_failed(
        _event(handlers_failed)
    )

    notification = notifier.sent[0][0]
    assert notification.exception is first
    assert notification.subject.endswith("ValueError: bad total.")
