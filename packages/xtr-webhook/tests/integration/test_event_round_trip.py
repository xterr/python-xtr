"""What crosses HTTP: the event's payload as the body, its name and id in the headers.

Every hop that writes the event is a real one: the send message crosses a serializing transport,
the transport posts the signed body, the endpoint reads it with the bundle's own parser, and the
consume message crosses a serializing transport again before the consumer is handed the event.
The posted bytes are compared with JSON written here, not by the code under test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import pytest
from xtr_clock import MockClock
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
from xtr_serializer import JsonEncoder, NotNormalizableValueError, PydanticNormalizer, Serializer

from tests.fixtures.events import DeliveryReport, Recipient
from tests.support.recording_message_bus import RecordingMessageBus
from tests.support.signed_requests import EVENT_ID, WHSEC, json_body, legacy_entry, standard_entry
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
_TIMESTAMP = int(_SENT_AT.timestamp())
_SERIALIZER = Serializer([PydanticNormalizer()], [JsonEncoder()])
_PAYLOAD: dict[str, object] = {
    "order": {"lines": [{"sku": "A-1", "qty": 2, "price": 9.75}], "gift": False, "note": None},
    "tags": ["eu", "vip"],
    "total": 19.5,
    "count": 2,
}
_EVENT = RemoteEvent("order.paid", EVENT_ID, _PAYLOAD)


class _Consumer:
    """Keeps what it was handed."""

    def __init__(self) -> None:
        self.consumed: list[RemoteEvent] = []

    async def consume(self, event: RemoteEvent) -> None:
        self.consumed.append(event)


def _posted_payload(event: RemoteEvent, fmt: SignatureFormat) -> dict[str, object]:
    """What the body holds: the payload, named under ``type`` where no signed header names it."""
    if fmt is SignatureFormat.LEGACY:
        return event.payload
    return {**event.payload, "type": event.name}


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


def _transport(client: MockHttpClient, fmt: SignatureFormat) -> Transport:
    return Transport(
        client,
        HeadersConfigurator(clock=MockClock(_SENT_AT), signature_format=fmt),
        JsonBodyConfigurator(_SERIALIZER, fmt),
        HeaderSignatureConfigurator(signature_format=fmt),
    )


async def _post(event: RemoteEvent, fmt: SignatureFormat) -> tuple[dict[str, str], bytes]:
    """Queue the webhook for ``event``, deliver what came off the queue, and return the request."""
    queued = await _over_the_wire(SendWebhookMessage(Subscriber("https://r.test/h", WHSEC), event))
    assert isinstance(queued, SendWebhookMessage)
    answer = MockResponse()
    await SendWebhookHandler(_transport(MockHttpClient(answer), fmt))(queued)
    sent = answer.get_request_options()
    return dict(cast("Mapping[str, str]", sent["headers"])), cast("bytes", sent["body"])


async def _receive(
    headers: Mapping[str, str], body: bytes, fmt: SignatureFormat
) -> tuple[int, str, list[object]]:
    """Answer the request at the endpoint; return the status, the answer and what it dispatched."""
    parser = RequestParser(signature_format=fmt, clock=MockClock(_SENT_AT))
    bus = RecordingMessageBus()
    controller = WebhookController({"shop": parser}, {"shop": WHSEC}, bus)
    answered = await controller.index_action(
        "shop", ServerRequest("POST", "/webhook/shop", headers, body), Response()
    )
    answer = (await answered.get_body().get_contents()).decode()
    return answered.get_status_code(), answer, bus.messages


async def _consumed(headers: Mapping[str, str], body: bytes, fmt: SignatureFormat) -> RemoteEvent:
    """Receive the request, carry what it dispatched over the bus, and return what was consumed."""
    status, _, (dispatched,) = await _receive(headers, body, fmt)
    assert status == 202
    consumed = await _over_the_wire(dispatched)
    assert isinstance(consumed, ConsumeRemoteEventMessage)
    consumer = _Consumer()
    await ConsumeRemoteEventHandler(ConsumerLocator({"shop": consumer}))(consumed)
    (received,) = consumer.consumed
    return received


@pytest.mark.parametrize("fmt", list(SignatureFormat))
async def test_the_posted_body_is_the_payload_signed_as_the_format_says(
    fmt: SignatureFormat,
) -> None:
    headers, body = await _post(_EVENT, fmt)

    legacy, standard = legacy_entry("order.paid", body), standard_entry(_TIMESTAMP, body)
    assert body == json_body(_posted_payload(_EVENT, fmt))
    assert headers["Webhook-Id"] == EVENT_ID
    assert headers["Webhook-Timestamp"] == str(_TIMESTAMP)
    assert headers.get("Webhook-Event") == (
        None if fmt is SignatureFormat.STANDARD else "order.paid"
    )
    expected = {
        SignatureFormat.LEGACY: legacy,
        SignatureFormat.STANDARD: standard,
        SignatureFormat.TRANSITIONAL: f"{legacy} {standard}",
    }
    assert headers["Webhook-Signature"] == expected[fmt]


@pytest.mark.parametrize("fmt", list(SignatureFormat))
async def test_the_consumer_gets_the_name_id_and_payload_that_were_sent(
    fmt: SignatureFormat,
) -> None:
    received = await _consumed(*await _post(_EVENT, fmt), fmt)

    assert received == RemoteEvent(_EVENT.name, _EVENT.id, _posted_payload(_EVENT, fmt))
    assert type(received) is RemoteEvent


async def test_an_event_of_a_class_of_its_own_crosses_http_as_its_payload_alone() -> None:
    report = DeliveryReport(
        "mailer",
        EVENT_ID,
        {"provider": "acme"},
        occurred_at=datetime(2026, 3, 1, 9, 30, tzinfo=ZoneInfo("Europe/Bucharest")),
        scheduled_for=datetime(2026, 10, 25, 3, 30, fold=1, tzinfo=ZoneInfo("Europe/Bucharest")),
        recipient=Recipient("ana@example.com", ("vip",)),
    )

    headers, body = await _post(report, SignatureFormat.LEGACY)
    received = await _consumed(headers, body, SignatureFormat.LEGACY)

    assert body == b'{"provider":"acme"}'
    assert received == RemoteEvent("mailer", EVENT_ID, {"provider": "acme"})
    assert type(received) is RemoteEvent


@pytest.mark.parametrize("fmt", list(SignatureFormat))
@pytest.mark.parametrize(
    "value",
    [datetime(2026, 3, 1, 9, 30), {"a", "b"}],  # noqa: DTZ001 — the naive datetime is the case.
    ids=["naive-datetime", "set"],
)
async def test_a_payload_value_the_serializer_refuses_fails_the_send_and_posts_nothing(
    value: object, fmt: SignatureFormat
) -> None:
    client = MockHttpClient(MockResponse())

    with pytest.raises(NotNormalizableValueError):
        await _transport(client, fmt).send(
            Subscriber("https://r.test/h", WHSEC),
            RemoteEvent("order.paid", EVENT_ID, {"at": value}),
        )

    assert client.get_requests_count() == 0


@pytest.mark.parametrize("fmt", list(SignatureFormat))
async def test_a_rewritten_body_is_refused_and_nothing_dispatched(fmt: SignatureFormat) -> None:
    headers, body = await _post(_EVENT, fmt)

    status, _, dispatched = await _receive(headers, body.replace(b"A-1", b"A-2"), fmt)

    assert (status, dispatched) == (406, [])


@pytest.mark.parametrize("fmt", list(SignatureFormat))
async def test_a_rewritten_id_is_refused_and_nothing_dispatched(fmt: SignatureFormat) -> None:
    headers, body = await _post(_EVENT, fmt)

    status, _, dispatched = await _receive({**headers, "Webhook-Id": "evt_other"}, body, fmt)

    assert (status, dispatched) == (406, [])


async def test_a_rewritten_timestamp_is_refused_by_the_standard_format() -> None:
    # Under the transitional format the legacy entry, which signs no timestamp, still verifies.
    headers, body = await _post(_EVENT, SignatureFormat.STANDARD)
    rewritten = {**headers, "Webhook-Timestamp": str(_TIMESTAMP + 1)}

    status, _, dispatched = await _receive(rewritten, body, SignatureFormat.STANDARD)

    assert (status, dispatched) == (406, [])


@pytest.mark.parametrize(
    "body",
    [b'["hidden-value"]', b'"hidden-value"', b'{"hidden-value', b'{"k":"hidden-value\xff"}'],
    ids=["an-array", "a-string", "garbled", "not-utf-8"],
)
async def test_a_signed_body_that_is_no_json_object_is_refused_without_being_echoed(
    body: bytes,
) -> None:
    headers = {
        "Content-Type": "application/json",
        "Webhook-Event": "order.paid",
        "Webhook-Id": EVENT_ID,
        "Webhook-Signature": legacy_entry("order.paid", body),
    }

    status, answer, dispatched = await _receive(headers, body, SignatureFormat.LEGACY)

    assert (status, dispatched) == (406, [])
    assert answer in {"Request body is malformed.", "Request does not match."}
