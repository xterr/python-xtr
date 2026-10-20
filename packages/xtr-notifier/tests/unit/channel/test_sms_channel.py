from __future__ import annotations

import pytest

from tests.support.fake_transport import FakeTransport
from tests.support.recording_message_bus import RecordingMessageBus
from xtr_notifier.channel import SmsChannel
from xtr_notifier.exception import LogicError
from xtr_notifier.message import SmsMessage
from xtr_notifier.notification import Notification, NotificationSummary
from xtr_notifier.recipient import NoRecipient, Recipient, SmsRecipientInterface

pytestmark = pytest.mark.anyio


class _OwnMessage(Notification):
    def as_sms_message(
        self, recipient: SmsRecipientInterface, transport_name: str | None
    ) -> SmsMessage | None:
        del transport_name
        return SmsMessage(recipient.phone, "short", from_="ACME")


async def test_it_texts_the_recipient_the_message_the_notification_makes() -> None:
    transport = FakeTransport()
    notification = Notification("Your code is 1234")

    await SmsChannel(transport).notify(notification, Recipient(phone="+3312345678"))

    assert transport.sent == [
        SmsMessage(
            "+3312345678",
            "Your code is 1234",
            notification=NotificationSummary.from_notification(notification),
        )
    ]


async def test_it_names_the_transport_it_was_asked_for() -> None:
    transport = FakeTransport()

    await SmsChannel(transport).notify(Notification("Hi"), Recipient(phone="+33"), "twilio")

    assert transport.sent[0].transport == "twilio"


async def test_it_sends_the_message_the_notification_renders_itself() -> None:
    transport = FakeTransport()

    await SmsChannel(transport).notify(_OwnMessage("Hi"), Recipient(phone="+33"))

    assert transport.sent == [SmsMessage("+33", "short", from_="ACME")]


async def test_it_queues_on_the_bus_when_it_has_one() -> None:
    bus = RecordingMessageBus()

    await SmsChannel(message_bus=bus).notify(Notification("Hi"), Recipient(phone="+33"))

    assert [type(message) for message in bus.messages] == [SmsMessage]


@pytest.mark.parametrize(
    ("recipient", "supported"),
    [
        (Recipient(phone="+33"), True),
        (Recipient("a@example.test"), False),
        (NoRecipient(), False),
    ],
)
def test_it_supports_a_recipient_with_a_phone_number(
    recipient: Recipient | NoRecipient, supported: bool
) -> None:
    assert SmsChannel(FakeTransport()).supports(Notification("Hi"), recipient) is supported


async def test_it_refuses_to_text_a_recipient_without_a_phone_number() -> None:
    with pytest.raises(LogicError) as caught:
        await SmsChannel(FakeTransport()).notify(Notification("Hi"), NoRecipient())

    assert str(caught.value) == '"SmsChannel" needs a recipient with a phone number.'
