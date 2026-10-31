"""An application's event, from the sender's bus through HTTP to the receiver's consumer, unchanged.

Every hop that writes the event is a real one: the send message crosses a serializing transport,
the transport posts the signed body, the endpoint reads it with the bundle's own parser, and the
consume message crosses a serializing transport again before the consumer is handed the event.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import pytest
from xtr_clock import DatePoint, MockClock
from xtr_http_client import MockHttpClient, MockResponse
from xtr_http_message import Response, ServerRequest
from xtr_messenger import (
    InMemoryTransport,
    InMemoryTransportFactory,
    JsonSerializer,
    MessageBusConfig,
    MessageBusFactory,
    TransportConfig,
)
from xtr_remote_event import ConsumerLocator, RemoteEvent
from xtr_remote_event.messenger import ConsumeRemoteEventHandler, ConsumeRemoteEventMessage
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

from tests.fixtures.events import DeliveryReport, Recipient
from tests.support.recording_message_bus import RecordingMessageBus
from tests.support.signed_requests import EVENT_ID, WHSEC, event_body, legacy_entry
from xtr_webhook.client import RequestParser
from xtr_webhook.controller import WebhookController
from xtr_webhook.messenger import SendWebhookHandler, SendWebhookMessage
from xtr_webhook.server import (
    HeadersConfigurator,
    HeaderSignatureConfigurator,
    JsonBodyConfigurator,
    SignatureFormat,
    Transport,
)
from xtr_webhook.subscriber import Subscriber

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio

_SENT_AT = datetime(2026, 10, 25, 1, 0, tzinfo=UTC)
_REPEATED_HOUR = datetime(2026, 10, 25, 3, 30, fold=1, tzinfo=ZoneInfo("Europe/Bucharest"))
_SERIALIZER = Serializer([PydanticNormalizer()], [JsonEncoder()])


class _Consumer:
    """Keeps what it was handed."""

    def __init__(self) -> None:
        self.consumed: list[RemoteEvent] = []

    async def consume(self, event: RemoteEvent) -> None:
        self.consumed.append(event)


def _report() -> DeliveryReport:
    return DeliveryReport(
        "mailer",
        "evt_7",
        {"provider": "acme", "attempt": 2},
        occurred_at=DatePoint(2026, 3, 1, 9, 30, tzinfo=ZoneInfo("Europe/Bucharest")),
        scheduled_for=_REPEATED_HOUR,
        recipient=Recipient("ana@example.com", ("vip",)),
        tags=("welcome", "eu"),
        metadata={"campaign": "spring", "locale": "ro"},
    )


async def _over_the_wire(message: object) -> object:
    """Send ``message`` through a serializing in-memory transport and return what came off it."""
    config = MessageBusConfig(
        transports={"mem": TransportConfig("in-memory://?serialize=true")},
        routing={type(message): "mem"},
    )
    factory = InMemoryTransportFactory(JsonSerializer(_SERIALIZER))
    transport = factory.create(config.transports)["mem"]
    assert isinstance(transport, InMemoryTransport)
    _ = await MessageBusFactory(config, [factory]).bus().dispatch(message)
    (received,) = [envelope.message async for envelope in transport.get()]
    return received


async def _post(event: RemoteEvent, fmt: SignatureFormat) -> tuple[dict[str, str], bytes]:
    """Queue the webhook for ``event``, deliver what came off the queue, and return the request."""
    queued = await _over_the_wire(SendWebhookMessage(Subscriber("https://r.test/h", WHSEC), event))
    assert isinstance(queued, SendWebhookMessage)
    answer = MockResponse()
    transport = Transport(
        MockHttpClient(answer),
        HeadersConfigurator(clock=MockClock(_SENT_AT), signature_format=fmt),
        JsonBodyConfigurator(_SERIALIZER),
        HeaderSignatureConfigurator(signature_format=fmt),
    )
    await SendWebhookHandler(transport)(queued)
    sent = answer.get_request_options()
    return dict(cast("Mapping[str, str]", sent["headers"])), cast("bytes", sent["body"])


async def _receive(
    headers: Mapping[str, str], body: bytes, fmt: SignatureFormat
) -> tuple[int, list[object]]:
    """Answer the request at the endpoint, and return the status and what it dispatched."""
    parser = RequestParser(_SERIALIZER, signature_format=fmt, clock=MockClock(_SENT_AT))
    bus = RecordingMessageBus()
    controller = WebhookController({"mailer": parser}, {"mailer": WHSEC}, bus)
    answered = await controller.index_action(
        "mailer", ServerRequest("POST", "/webhook/mailer", headers, body), Response()
    )
    return answered.get_status_code(), bus.messages


@pytest.mark.parametrize("fmt", list(SignatureFormat))
async def test_the_consumer_is_handed_the_event_that_was_sent(fmt: SignatureFormat) -> None:
    sent = _report()
    headers, body = await _post(sent, fmt)
    status, (dispatched,) = await _receive(headers, body, fmt)
    consumed = await _over_the_wire(dispatched)
    consumer = _Consumer()

    assert isinstance(consumed, ConsumeRemoteEventMessage)
    await ConsumeRemoteEventHandler(ConsumerLocator({"mailer": consumer}))(consumed)

    assert status == 202
    assert consumer.consumed == [sent]
    (received,) = consumer.consumed
    assert type(received) is DeliveryReport
    assert type(received.recipient) is Recipient
    assert (received.scheduled_for.tzinfo, received.scheduled_for.fold) == (
        ZoneInfo("Europe/Bucharest"),
        1,
    )


@pytest.mark.parametrize("fmt", list(SignatureFormat))
async def test_the_signature_covers_the_bytes_that_were_posted(fmt: SignatureFormat) -> None:
    headers, body = await _post(_report(), fmt)

    answer = await _receive(headers, body.replace(b"vip", b"VIP"), fmt)

    assert answer == (406, [])


@pytest.mark.parametrize(
    "tag", ["nowhere", "webhook_test_stray_notice"], ids=["unknown", "another-hierarchy"]
)
async def test_a_signed_body_tagged_with_no_event_class_is_refused_and_nothing_dispatched(
    tag: str,
) -> None:
    body = event_body(tag=tag)
    headers = {
        "Content-Type": "application/json",
        "Webhook-Event": "event-name",
        "Webhook-Id": EVENT_ID,
        "Webhook-Signature": legacy_entry("event-name", body),
    }

    answer = await _receive(headers, body, SignatureFormat.LEGACY)

    assert answer == (406, [])
