from __future__ import annotations

import pytest
from typing_extensions import override

from tests.support.fake_transport import FakeTransport
from tests.support.recording_message_bus import RecordingMessageBus
from xtr_notifier.channel import ChatChannel
from xtr_notifier.message import ChatMessage, MessageOptions
from xtr_notifier.notification import Notification, NotificationSummary
from xtr_notifier.recipient import NoRecipient, Recipient, RecipientInterface

pytestmark = pytest.mark.anyio


class _OwnMessage(Notification):
    def as_chat_message(
        self, recipient: RecipientInterface, transport_name: str | None
    ) -> ChatMessage | None:
        if isinstance(recipient, NoRecipient):
            return None
        return ChatMessage(f"to {transport_name}", MessageOptions("slack", "ops"))


class _NoChannels(Notification):
    @override
    def get_channels(self, recipient: RecipientInterface) -> tuple[str, ...]:
        return ()


async def test_it_sends_the_message_the_notification_makes_by_default() -> None:
    transport = FakeTransport()
    notification = Notification("Disk full")

    await ChatChannel(transport).notify(notification, NoRecipient())

    assert transport.sent == [
        ChatMessage("Disk full", notification=NotificationSummary.from_notification(notification))
    ]


async def test_it_names_the_transport_it_was_asked_for() -> None:
    transport = FakeTransport()

    await ChatChannel(transport).notify(Notification("Hello"), NoRecipient(), "slack")

    sent = transport.sent[0]
    assert sent.transport == "slack"


async def test_it_sends_the_message_the_notification_renders_itself() -> None:
    transport = FakeTransport()

    await ChatChannel(transport).notify(_OwnMessage("Hello"), Recipient("a@example.test"), "slack")

    assert transport.sent == [ChatMessage("to slack", MessageOptions("slack", "ops"), "slack")]


async def test_it_falls_back_to_the_default_when_the_notification_renders_nothing() -> None:
    transport = FakeTransport()

    await ChatChannel(transport).notify(_OwnMessage("Hello"), NoRecipient())

    assert [message.subject for message in transport.sent] == ["Hello"]


async def test_it_queues_on_the_bus_when_it_has_one() -> None:
    bus = RecordingMessageBus()

    await ChatChannel(message_bus=bus).notify(_NoChannels("Hello"), NoRecipient(), "slack")

    assert len(bus.messages) == 1
    queued = bus.messages[0]
    assert isinstance(queued, ChatMessage)
    assert queued.transport == "slack"


def test_it_supports_every_recipient() -> None:
    channel = ChatChannel(FakeTransport())

    assert channel.supports(Notification("Hello"), NoRecipient())
    assert channel.supports(Notification("Hello"), Recipient("a@example.test"))
