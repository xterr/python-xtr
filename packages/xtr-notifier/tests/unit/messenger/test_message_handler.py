from __future__ import annotations

import pytest
from xtr_messenger import HandlersLocator

from tests.support.fake_transport import FakeTransport
from xtr_notifier.message import ChatMessage, PushMessage, SmsMessage
from xtr_notifier.messenger import MessageHandler


@pytest.mark.anyio
@pytest.mark.parametrize(
    "message",
    [ChatMessage("Hello"), SmsMessage("+33", "Hello"), PushMessage("Hello", "World")],
)
async def test_it_sends_a_queued_message_through_its_transport(
    message: ChatMessage | SmsMessage | PushMessage,
) -> None:
    transport = FakeTransport("slack")

    sent = await MessageHandler(transport)(message)

    assert transport.sent == [message]
    assert sent.transport == "slack"


@pytest.mark.parametrize("message_type", [ChatMessage, SmsMessage, PushMessage])
def test_the_bus_accepts_it_as_the_handler_of_each_message(message_type: type) -> None:
    handlers = HandlersLocator()

    descriptor = handlers.register(message_type, MessageHandler(FakeTransport()))

    assert descriptor.name
