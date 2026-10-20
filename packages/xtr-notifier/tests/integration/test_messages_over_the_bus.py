"""Messages survive the wire of a message bus, and come back to be sent.

A queued message is encoded by one process and decoded by another, so every
field — the provider's options, the summary of the notification — has to come
back equal, or the provider renders something else than what was queued.
"""

from __future__ import annotations

import pytest
from xtr_messenger import (
    DataclassCodec,
    HandlersLocator,
    InMemoryTransport,
    InMemoryTransportFactory,
    MessageBusConfig,
    MessageBusFactory,
    TransportConfig,
)

from tests.support.fake_transport import FakeTransport
from xtr_notifier import Chatter, Texter
from xtr_notifier.message import (
    ChatMessage,
    MessageInterface,
    MessageOptions,
    PushMessage,
    SmsMessage,
)
from xtr_notifier.messenger import MessageHandler
from xtr_notifier.notification import Importance, Notification
from xtr_notifier.recipient import Recipient

_OPTIONS = MessageOptions(
    "slack",
    "ops",
    {"blocks": [{"type": "section", "fields": [1, 2.5, None]}], "unfurl": True, "ts": "1.2"},
)


def _notification() -> Notification:
    return Notification(
        "Disk full",
        content="98% used",
        importance=Importance.URGENT,
        exception=RuntimeError("no space left"),
    )


def _messages() -> list[MessageInterface]:
    notification = _notification()
    return [
        ChatMessage.from_notification(notification).with_options(_OPTIONS).with_transport("slack"),
        SmsMessage.from_notification(notification, Recipient(phone="+3312345678"))
        .with_from("ACME")
        .with_options(MessageOptions("twilio"))
        .with_transport("twilio"),
        PushMessage.from_notification(notification).with_options(MessageOptions("ntfy", "topic")),
    ]


@pytest.mark.parametrize("message", _messages(), ids=["chat", "sms", "push"])
@pytest.mark.parametrize("forbid_unknown_fields", [False, True])
def test_the_codec_brings_every_field_back(
    message: MessageInterface, forbid_unknown_fields: bool
) -> None:
    codec = DataclassCodec(forbid_unknown_fields=forbid_unknown_fields)

    decoded = codec.decode(type(message), codec.encode(message))

    assert decoded == message


@pytest.mark.anyio
async def test_a_message_dispatched_comes_back_off_the_wire_unchanged() -> None:
    config = MessageBusConfig(
        transports={"mem": TransportConfig("in-memory://?serialize=true")},
        routing={ChatMessage: "mem", SmsMessage: "mem", PushMessage: "mem"},
    )
    factories = [InMemoryTransportFactory()]
    recorder = factories[0].create(config.transports)["mem"]
    assert isinstance(recorder, InMemoryTransport)
    bus = MessageBusFactory(config, factories).bus()
    messages = _messages()

    for message in messages:
        _ = await bus.dispatch(message)
    received = [envelope.message async for envelope in recorder.get()]

    assert received == messages


@pytest.mark.anyio
async def test_a_message_queued_by_the_chatter_and_the_texter_is_sent_by_the_handler() -> None:
    chat_transport, text_transport = FakeTransport("chat"), FakeTransport("text")
    handlers = HandlersLocator()
    _ = handlers.register(ChatMessage, MessageHandler(chat_transport))
    _ = handlers.register(SmsMessage, MessageHandler(text_transport))
    _ = handlers.register(PushMessage, MessageHandler(text_transport))
    bus = MessageBusFactory(MessageBusConfig(handle_unrouted=True), handlers=handlers).bus()
    chat, sms, push = _messages()

    assert await Chatter(chat_transport, bus).send(chat) is None
    assert await Texter(text_transport, bus).send(sms) is None
    assert await Texter(text_transport, bus).send(push) is None

    assert chat_transport.sent == [chat]
    assert text_transport.sent == [sms, push]
