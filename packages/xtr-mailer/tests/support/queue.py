"""A message bus queuing on a serializing in-memory transport, as a real broker would carry it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_messenger import (
    InMemoryTransport,
    InMemoryTransportFactory,
    JsonSerializer,
    MessageBusConfig,
    MessageBusFactory,
    TransportConfig,
    register_message,
)
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

from xtr_mailer import Mailer
from xtr_mailer.messenger import SendEmailMessage
from xtr_mailer.transport import NullTransport

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_mime import RawMessage

    from xtr_mailer import Envelope

__all__ = ["WIRE", "through_the_queue"]

# Declared as a bus that decodes queued email does; the bundle declares it for an application.
register_message(SendEmailMessage)

WIRE = JsonSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]))


async def through_the_queue(
    message: RawMessage,
    envelope: Envelope | None = None,
    event_dispatcher: EventDispatcherInterface | None = None,
) -> SendEmailMessage:
    """Queue ``message`` with a mailer, and return what a worker takes off the queue."""
    config = MessageBusConfig(
        transports={"mem": TransportConfig("in-memory://?serialize=true")},
        routing={SendEmailMessage: "mem"},
    )
    factory = InMemoryTransportFactory(WIRE)
    transport = factory.create(config.transports)["mem"]
    assert isinstance(transport, InMemoryTransport)
    bus = MessageBusFactory(config, [factory]).bus()
    await Mailer(NullTransport(), bus, event_dispatcher).send(message, envelope)
    (received,) = [queued.message async for queued in transport.get()]
    assert isinstance(received, SendEmailMessage)
    return received
