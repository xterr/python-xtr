"""What the message survives on a real bus: the wire out, and a type nothing consumes."""

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
from xtr_remote_event.consumer import ConsumerLocator
from xtr_remote_event.exception import LogicError
from xtr_remote_event.messenger import ConsumeRemoteEventHandler, ConsumeRemoteEventMessage


def _recorder() -> tuple[MessageBusFactory, InMemoryTransport]:
    """Return a bus factory routing the message to a recorder, and that recorder."""
    config = MessageBusConfig(
        transports={"mem": TransportConfig("in-memory://?serialize=true")},
        routing={ConsumeRemoteEventMessage: "mem"},
    )
    factories = [InMemoryTransportFactory()]
    transport = factories[0].create(config.transports)["mem"]
    assert isinstance(transport, InMemoryTransport)
    return MessageBusFactory(config, factories), transport


@pytest.mark.anyio
async def test_a_dispatched_message_comes_back_off_the_wire_unchanged() -> None:
    factory, transport = _recorder()
    message = ConsumeRemoteEventMessage(
        "stripe",
        RemoteEvent("stripe", "evt_1", {"amount": 500, "currency": "eur", "livemode": True}),
    )

    _ = await factory.bus().dispatch(message)
    received = [envelope.message async for envelope in transport.get()]

    assert received == [message]
    decoded = received[0]
    assert isinstance(decoded, ConsumeRemoteEventMessage)
    assert decoded.event == message.event
    assert decoded.event.payload == {"amount": 500, "currency": "eur", "livemode": True}


@pytest.mark.anyio
async def test_a_message_for_a_type_nothing_consumes_fails_the_dispatch() -> None:
    handlers = HandlersLocator()
    _ = handlers.register(ConsumeRemoteEventMessage, ConsumeRemoteEventHandler(ConsumerLocator({})))
    bus = MessageBusFactory(MessageBusConfig(handle_unrouted=True), handlers=handlers).bus()

    with pytest.raises(HandlersFailedError) as caught:
        _ = await bus.dispatch(
            ConsumeRemoteEventMessage("mailgun", RemoteEvent("mailgun", "evt_1", {}))
        )

    (failure,) = caught.value.errors.values()
    assert isinstance(failure, LogicError)
    assert str(failure) == 'Unable to find a consumer for message of type "mailgun".'
