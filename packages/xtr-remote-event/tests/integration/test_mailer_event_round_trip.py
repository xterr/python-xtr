"""What a mail provider's report survives on a serializing bus, and what read off it is refused."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from xtr_messenger import (
    EncodedEnvelope,
    InMemoryTransport,
    InMemoryTransportFactory,
    JsonSerializer,
    MessageBusConfig,
    MessageBusFactory,
    MessageDecodingFailedError,
    TransportConfig,
    name_of,
)
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

from xtr_remote_event import MailerDeliveryEvent, MailerEngagementEvent, RemoteEvent
from xtr_remote_event.messenger import ConsumeRemoteEventMessage

_DATE = datetime(2026, 3, 1, 9, 30, 15, 123456, tzinfo=UTC)

_FORGED = "forged-tag-from-the-wire"


def _wire() -> JsonSerializer:
    return JsonSerializer(Serializer([PydanticNormalizer()], [JsonEncoder()]))


async def _through_the_wire(event: RemoteEvent) -> ConsumeRemoteEventMessage:
    config = MessageBusConfig(
        transports={"mem": TransportConfig("in-memory://?serialize=true")},
        routing={ConsumeRemoteEventMessage: "mem"},
    )
    factories = [InMemoryTransportFactory(_wire())]
    transport = factories[0].create(config.transports)["mem"]
    assert isinstance(transport, InMemoryTransport)
    bus = MessageBusFactory(config, factories).bus()
    _ = await bus.dispatch(ConsumeRemoteEventMessage("mailgun", event))
    (received,) = [envelope.message async for envelope in transport.get()]
    assert isinstance(received, ConsumeRemoteEventMessage)
    return received


def _bounce() -> MailerDeliveryEvent:
    return MailerDeliveryEvent(
        MailerDeliveryEvent.BOUNCE,
        "evt_1",
        {"event": "failed", "severity": "permanent"},
        date=_DATE,
        recipient_email="jane@example.com",
        metadata={"order_id": "7", "attempt": 2},
        tags=("receipt", "eu"),
        reason="550 No such user",
    )


def _click() -> MailerEngagementEvent:
    return MailerEngagementEvent(
        MailerEngagementEvent.CLICK,
        "evt_2",
        {"event": "clicked", "url": "https://example.com/offer"},
        date=_DATE,
        recipient_email="jane@example.com",
        metadata={"campaign": "spring"},
        tags=("newsletter",),
    )


@pytest.mark.anyio
@pytest.mark.parametrize("event", [_bounce(), _click()], ids=["delivery", "engagement"])
async def test_a_mailer_event_comes_back_equal(event: RemoteEvent) -> None:
    received = await _through_the_wire(event)

    assert received.event == event


@pytest.mark.anyio
@pytest.mark.parametrize("event", [_bounce(), _click()], ids=["delivery", "engagement"])
async def test_a_mailer_event_comes_back_of_its_own_type(event: RemoteEvent) -> None:
    received = await _through_the_wire(event)

    assert type(received.event) is type(event)


def _arriving(event: dict[str, object]) -> EncodedEnvelope:
    return EncodedEnvelope(
        body=json.dumps({"type": "mailgun", "event": event}),
        headers={"type": name_of(ConsumeRemoteEventMessage)},
    )


def _delivery(tag: object) -> dict[str, object]:
    return {
        "$type": tag,
        "name": "bounce",
        "id": "evt_1",
        "payload": {},
        "date": _DATE.isoformat(),
        "reason": "550 No such user",
    }


def test_a_delivery_tagged_with_its_name_is_read_as_one() -> None:
    decoded = _wire().decode(_arriving(_delivery("mailer_delivery"))).message

    assert isinstance(decoded, ConsumeRemoteEventMessage)
    assert decoded.event == MailerDeliveryEvent(
        "bounce", "evt_1", {}, date=_DATE, reason="550 No such user"
    )


@pytest.mark.parametrize(
    "event",
    [
        _delivery(_FORGED),
        _delivery("AbstractMailerEvent"),
        _delivery("abstract_mailer_event"),
        {key: value for key, value in _delivery("mailer_delivery").items() if key != "date"},
    ],
    ids=["unknown-name", "abstract-class", "abstract-name", "no-date"],
)
def test_a_mailer_event_the_hierarchy_cannot_read_is_refused(event: dict[str, object]) -> None:
    with pytest.raises(MessageDecodingFailedError) as refused:
        _ = _wire().decode(_arriving(event))

    assert _FORGED not in str(refused.value)
