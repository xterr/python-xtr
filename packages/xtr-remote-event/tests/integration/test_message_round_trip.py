"""What the message survives on a real bus: the wire out, and a type nothing consumes."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from xtr_clock import DatePoint
from xtr_messenger import (
    HandlersFailedError,
    HandlersLocator,
    InMemoryTransport,
    InMemoryTransportFactory,
    JsonSerializer,
    MessageBusConfig,
    MessageBusFactory,
    MessageEncodingFailedError,
    TransportConfig,
)
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

from tests.fixtures.events import DeliveryReport, Recipient, UnnamedEvent
from xtr_remote_event import RemoteEvent
from xtr_remote_event.consumer import ConsumerLocator
from xtr_remote_event.exception import LogicError
from xtr_remote_event.messenger import ConsumeRemoteEventHandler, ConsumeRemoteEventMessage

_REPEATED_HOUR = datetime(2026, 10, 25, 3, 30, fold=1, tzinfo=ZoneInfo("Europe/Bucharest"))
"""The second 03:30 of the night the clocks go back: told apart from the first by its fold."""


def _recorder() -> tuple[MessageBusFactory, InMemoryTransport]:
    """Return a bus factory routing the message to a recorder, and that recorder."""
    config = MessageBusConfig(
        transports={"mem": TransportConfig("in-memory://?serialize=true")},
        routing={ConsumeRemoteEventMessage: "mem"},
    )
    wire = JsonSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]))
    factories = [InMemoryTransportFactory(wire)]
    transport = factories[0].create(config.transports)["mem"]
    assert isinstance(transport, InMemoryTransport)
    return MessageBusFactory(config, factories), transport


def _report() -> DeliveryReport:
    return DeliveryReport(
        "mailer",
        "evt_7",
        {"provider": "acme", "attempt": 2},
        occurred_at=DatePoint(2026, 3, 1, 9, 30, tzinfo=UTC),
        scheduled_for=_REPEATED_HOUR,
        recipient=Recipient("ana@example.com", ("vip",)),
        tags=("welcome", "eu"),
        metadata={"campaign": "spring", "locale": "ro"},
    )


async def _through_the_wire(message: ConsumeRemoteEventMessage) -> ConsumeRemoteEventMessage:
    factory, transport = _recorder()
    _ = await factory.bus().dispatch(message)
    (received,) = [envelope.message async for envelope in transport.get()]
    assert isinstance(received, ConsumeRemoteEventMessage)
    return received


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
async def test_a_plain_event_comes_back_a_plain_event() -> None:
    received = await _through_the_wire(
        ConsumeRemoteEventMessage("stripe", RemoteEvent("stripe", "evt_1", {}))
    )

    assert type(received.event) is RemoteEvent


@pytest.mark.anyio
async def test_an_application_event_comes_back_equal() -> None:
    message = ConsumeRemoteEventMessage("mailer", _report())

    received = await _through_the_wire(message)

    assert received == message


@pytest.mark.anyio
async def test_an_application_event_comes_back_of_its_own_class() -> None:
    received = await _through_the_wire(ConsumeRemoteEventMessage("mailer", _report()))

    assert type(received.event) is DeliveryReport
    assert type(received.event.recipient) is Recipient


@pytest.mark.anyio
async def test_a_date_in_the_repeated_hour_keeps_its_zone_and_fold() -> None:
    received = await _through_the_wire(ConsumeRemoteEventMessage("mailer", _report()))

    assert isinstance(received.event, DeliveryReport)
    scheduled = received.event.scheduled_for
    assert (scheduled, scheduled.tzinfo, scheduled.fold) == (
        _REPEATED_HOUR,
        ZoneInfo("Europe/Bucharest"),
        1,
    )


@pytest.mark.anyio
async def test_a_date_point_comes_back_as_the_datetime_it_is_declared() -> None:
    received = await _through_the_wire(ConsumeRemoteEventMessage("mailer", _report()))

    assert isinstance(received.event, DeliveryReport)
    assert received.event.occurred_at == datetime(2026, 3, 1, 9, 30, tzinfo=UTC)
    assert type(received.event.occurred_at) is datetime


@pytest.mark.anyio
async def test_an_event_of_a_class_with_no_name_is_refused_rather_than_sent_as_its_base() -> None:
    factory, _ = _recorder()
    message = ConsumeRemoteEventMessage("mailer", UnnamedEvent("mailer", "evt_1", {}, "soft"))

    with pytest.raises(MessageEncodingFailedError):
        _ = await factory.bus().dispatch(message)


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
