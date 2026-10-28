from __future__ import annotations

import pytest

from tests.support.fake_transport import FakeTransport
from tests.support.recording_message_bus import RecordingMessageBus
from xtr_notifier.channel import PushChannel
from xtr_notifier.message import PushMessage
from xtr_notifier.notification import Notification, NotificationSummary
from xtr_notifier.recipient import NoRecipient, RecipientInterface

pytestmark = pytest.mark.anyio


class _OwnMessage(Notification):
    def as_push_message(
        self, recipient: RecipientInterface, transport_name: str | None
    ) -> PushMessage | None:
        del recipient, transport_name
        return PushMessage("title", "body")


async def test_it_pushes_the_message_the_notification_makes_by_default() -> None:
    transport = FakeTransport()
    notification = Notification("Order shipped", content="On its way")

    await PushChannel(transport).notify(notification, NoRecipient())

    assert transport.sent == [
        PushMessage(
            "Order shipped",
            "On its way",
            notification=NotificationSummary.from_notification(notification),
        )
    ]


async def test_it_names_the_transport_it_was_asked_for() -> None:
    transport = FakeTransport()

    await PushChannel(transport).notify(Notification("Hi"), NoRecipient(), "ntfy")

    assert transport.sent[0].transport == "ntfy"


async def test_it_sends_the_message_the_notification_renders_itself() -> None:
    transport = FakeTransport()

    await PushChannel(transport).notify(_OwnMessage("Hi"), NoRecipient())

    assert transport.sent == [PushMessage("title", "body")]


async def test_it_queues_on_the_bus_when_it_has_one() -> None:
    bus = RecordingMessageBus()

    await PushChannel(message_bus=bus).notify(Notification("Hi"), NoRecipient())

    assert [type(message) for message in bus.messages] == [PushMessage]


def test_it_supports_every_recipient() -> None:
    assert PushChannel(FakeTransport()).supports(Notification("Hi"), NoRecipient())
