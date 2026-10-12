"""What the send message survives on a real bus: the wire out, and a refused delivery."""

from __future__ import annotations

import pytest
from xtr_messenger import (
    HandlersFailedError,
    HandlersLocator,
    InMemoryTransport,
    InMemoryTransportFactory,
    MessageBusConfig,
    MessageBusFactory,
    TransportConfig,
)
from xtr_remote_event import RemoteEvent

from tests.support.fake_transport import FakeTransport
from xtr_webhook.exception import DeliveryError
from xtr_webhook.messenger import SendWebhookHandler, SendWebhookMessage
from xtr_webhook.subscriber import Subscriber

pytestmark = pytest.mark.anyio

_SIGNING_KEY = "s3cr3t"
"""What the subscriber signs with, kept here so the wire can be checked against it."""


def _recorder() -> tuple[MessageBusFactory, InMemoryTransport]:
    """Return a bus factory routing the message to a recorder, and that recorder."""
    config = MessageBusConfig(
        transports={"mem": TransportConfig("in-memory://?serialize=true")},
        routing={SendWebhookMessage: "mem"},
    )
    factories = [InMemoryTransportFactory()]
    transport = factories[0].create(config.transports)["mem"]
    assert isinstance(transport, InMemoryTransport)
    return MessageBusFactory(config, factories), transport


def _bus(transport: FakeTransport) -> MessageBusFactory:
    """Return a bus factory handling the message in-process with ``transport``."""
    handlers = HandlersLocator()
    _ = handlers.register(SendWebhookMessage, SendWebhookHandler(transport))
    return MessageBusFactory(MessageBusConfig(handle_unrouted=True), handlers=handlers)


def _message() -> SendWebhookMessage:
    return SendWebhookMessage(
        Subscriber("https://receiver.test/hook", _SIGNING_KEY),
        RemoteEvent("order.created", "evt_1", {"total": 500, "currency": "eur", "paid": True}),
    )


async def test_a_dispatched_message_comes_back_off_the_wire_unchanged() -> None:
    factory, recorder = _recorder()
    message = _message()

    _ = await factory.bus().dispatch(message)
    received = [envelope.message async for envelope in recorder.get()]

    assert received == [message]


async def test_the_subscriber_and_the_event_survive_the_wire() -> None:
    factory, recorder = _recorder()
    message = _message()

    _ = await factory.bus().dispatch(message)
    decoded = next(iter([envelope.message async for envelope in recorder.get()]))

    assert isinstance(decoded, SendWebhookMessage)
    assert decoded.subscriber == message.subscriber
    assert decoded.event == message.event
    assert decoded.event.payload == {"total": 500, "currency": "eur", "paid": True}


async def test_the_secret_crosses_the_wire_so_the_delivery_can_be_signed() -> None:
    factory, recorder = _recorder()

    _ = await factory.bus().dispatch(_message())
    decoded = next(iter([envelope.message async for envelope in recorder.get()]))

    assert isinstance(decoded, SendWebhookMessage)
    assert decoded.subscriber.secret == _SIGNING_KEY


async def test_dispatching_it_delivers_through_the_transport() -> None:
    transport = FakeTransport()
    message = _message()

    _ = await _bus(transport).bus().dispatch(message)

    assert transport.sends == [(message.subscriber, message.event)]


async def test_a_refused_delivery_fails_the_dispatch() -> None:
    refusal = DeliveryError(500, "https://receiver.test/hook")

    with pytest.raises(HandlersFailedError) as caught:
        _ = await _bus(FakeTransport(raises=refusal)).bus().dispatch(_message())

    (failure,) = caught.value.errors.values()
    assert failure is refusal
    assert str(failure) == 'The webhook to "https://receiver.test/hook" was answered with HTTP 500.'
