"""What the parser claims and reads, and the legacy signature; the Standard one is beside it."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from xtr_clock import MockClock
from xtr_http_message import ServerRequest
from xtr_remote_event import RemoteEvent
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

from tests.fixtures.events import DeliveryReport, Recipient
from tests.support.signed_requests import EVENT_ID, WHSEC, arriving, event_body, legacy_entry
from xtr_webhook.client import RequestParser
from xtr_webhook.exception import InvalidArgumentError, RejectWebhookError

_MALFORMED = "Request body is malformed."
_FORGED = "forged-tag-from-the-wire"


def _parser() -> RequestParser:
    serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])
    return RequestParser(serializer, clock=MockClock(datetime(2026, 1, 1, tzinfo=UTC)))


def _signed(body: bytes, event_name: str = "event-name") -> ServerRequest:
    return arriving(
        body,
        {
            "Webhook-Signature": legacy_entry(event_name, body),
            "Webhook-Event": event_name,
            "Webhook-Id": EVENT_ID,
        },
    )


@pytest.mark.anyio
async def test_it_refuses_a_request_its_matcher_does_not_claim() -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(ServerRequest("GET", "/"), WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == "Request does not match."


@pytest.mark.anyio
async def test_it_refuses_a_body_that_is_not_json_whatever_the_media_type_says() -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(_signed(b"{not json at all"), WHSEC)

    assert str(refused.value) == "Request does not match."


@pytest.mark.anyio
async def test_it_claims_a_json_body_that_announces_no_media_type() -> None:
    body = event_body(payload={"foo": "bar"})
    headers = {
        "Webhook-Signature": legacy_entry("event-name", body),
        "Webhook-Event": "event-name",
        "Webhook-Id": EVENT_ID,
    }

    parsed = await _parser().parse(ServerRequest("POST", "/", headers, body), WHSEC)

    assert parsed == RemoteEvent("event-name", EVENT_ID, {"foo": "bar"})


@pytest.mark.anyio
async def test_it_reads_the_event_the_body_holds() -> None:
    parsed = await _parser().parse(_signed(event_body(payload={"foo": "bar"})), WHSEC)

    assert parsed == RemoteEvent("event-name", EVENT_ID, {"foo": "bar"})
    assert type(parsed) is RemoteEvent


@pytest.mark.anyio
async def test_it_reads_an_event_of_a_class_of_the_hierarchy_as_that_class() -> None:
    sent = DeliveryReport(
        "mailer",
        EVENT_ID,
        {},
        occurred_at=datetime(2026, 3, 1, 9, tzinfo=UTC),
        scheduled_for=datetime(2026, 10, 25, 3, 30, fold=1, tzinfo=ZoneInfo("Europe/Bucharest")),
        recipient=Recipient("ana@example.com"),
    )
    serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])
    body = serializer.serialize(sent, "json", type_=RemoteEvent).encode()

    parsed = await _parser().parse(_signed(body, "mailer"), WHSEC)

    assert parsed == sent
    assert type(parsed) is DeliveryReport


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body",
    [
        b"1",
        b"[1, 2]",
        event_body(tag=_FORGED),
        event_body(tag="webhook_test_stray_notice"),
        event_body(tag=None),
        json.dumps({"name": "event-name", "id": EVENT_ID, "payload": {}}).encode(),
        json.dumps({"$type": "remote_event", "name": _FORGED}).encode(),
        json.dumps({"$type": "remote_event", "name": 1, "id": EVENT_ID, "payload": {}}).encode(),
    ],
    ids=[
        "a-number",
        "an-array",
        "an-unknown-tag",
        "the-tag-of-another-hierarchy",
        "a-tag-that-is-no-name",
        "no-tag",
        "missing-fields",
        "a-field-of-the-wrong-type",
    ],
)
async def test_a_genuine_body_that_holds_no_event_is_refused_as_malformed(body: bytes) -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(_signed(body), WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == _MALFORMED
    assert refused.value.__cause__ is None
    assert refused.value.__context__ is None


@pytest.mark.anyio
async def test_a_wrong_signature_is_answered_before_the_body_is_read() -> None:
    body = event_body(tag=_FORGED)
    request = arriving(
        body,
        {
            "Webhook-Signature": legacy_entry("event-name", body, key="wrong-value"),
            "Webhook-Event": "event-name",
            "Webhook-Id": EVENT_ID,
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(request, WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_legacy_rejects_a_rewritten_event_header() -> None:
    body = event_body()
    request = arriving(
        body,
        {
            "Webhook-Signature": legacy_entry("event-name", body),
            "Webhook-Event": "rewritten-name",
            "Webhook-Id": EVENT_ID,
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(request, WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_legacy_requires_the_event_header() -> None:
    body = event_body()
    request = arriving(
        body, {"Webhook-Signature": legacy_entry("event-name", body), "Webhook-Id": EVENT_ID}
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(request, WHSEC)

    assert str(refused.value) == 'Missing "Webhook-Event" HTTP request signature header.'


@pytest.mark.anyio
async def test_an_empty_secret_is_a_misconfiguration_not_a_refusal() -> None:
    with pytest.raises(InvalidArgumentError) as misconfigured:
        _ = await _parser().parse(arriving(b"{}"), "")

    assert str(misconfigured.value) == "A non-empty secret is required."


def test_an_algorithm_this_runtime_cannot_make_is_refused_where_it_is_configured() -> None:
    serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])

    with pytest.raises(InvalidArgumentError) as misconfigured:
        _ = RequestParser(serializer, algorithm="not-a-digest")

    assert str(misconfigured.value) == 'The signing algorithm "not-a-digest" is not available.'
