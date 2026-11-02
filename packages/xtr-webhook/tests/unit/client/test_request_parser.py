"""What the parser claims and reads, and the legacy signature; the Standard one is beside it."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from xtr_clock import MockClock
from xtr_http_message import ServerRequest
from xtr_remote_event import RemoteEvent

from tests.support.signed_requests import EVENT_ID, WHSEC, arriving, json_body, legacy_entry
from xtr_webhook.client import RequestParser
from xtr_webhook.exception import InvalidArgumentError, RejectWebhookError

_MALFORMED = "Request body is malformed."
_PAYLOAD: dict[str, object] = {
    "order": {"lines": [{"sku": "A-1", "qty": 2}], "note": None},
    "total": 42.5,
    "paid": True,
}


def _parser() -> RequestParser:
    return RequestParser(clock=MockClock(datetime(2026, 1, 1, tzinfo=UTC)))


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
@pytest.mark.parametrize(
    "body", [b"{not json at all", b'{"a":"\xff"}'], ids=["garbled", "not-utf-8"]
)
async def test_it_refuses_a_body_that_is_not_json_whatever_the_media_type_says(
    body: bytes,
) -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(_signed(body), WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == "Request does not match."


@pytest.mark.anyio
async def test_it_claims_a_json_body_that_announces_no_media_type() -> None:
    body = json_body({"foo": "bar"})
    headers = {
        "Webhook-Signature": legacy_entry("event-name", body),
        "Webhook-Event": "event-name",
        "Webhook-Id": EVENT_ID,
    }

    parsed = await _parser().parse(ServerRequest("POST", "/", headers, body), WHSEC)

    assert parsed == RemoteEvent("event-name", EVENT_ID, {"foo": "bar"})


@pytest.mark.anyio
async def test_legacy_reads_the_name_and_id_from_the_headers_and_the_payload_from_the_body() -> (
    None
):
    parsed = await _parser().parse(_signed(json_body(_PAYLOAD), "order.paid"), WHSEC)

    assert parsed == RemoteEvent("order.paid", EVENT_ID, _PAYLOAD)
    assert type(parsed) is RemoteEvent


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body",
    [b"1", b"[1,2]", b'"text"', b"null", b"true"],
    ids=["a-number", "an-array", "a-string", "null", "a-boolean"],
)
async def test_a_genuine_body_that_is_not_an_object_is_refused_as_malformed(body: bytes) -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(_signed(body), WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == _MALFORMED
    assert refused.value.__cause__ is None
    assert refused.value.__context__ is None


@pytest.mark.anyio
async def test_a_wrong_signature_is_answered_before_the_body_is_read() -> None:
    body = b"[1,2]"
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
@pytest.mark.parametrize(
    "rewritten",
    [{"Webhook-Event": "rewritten-name"}, {"Webhook-Id": "rewritten-id"}],
    ids=["event", "id"],
)
async def test_legacy_rejects_a_rewritten_header(rewritten: dict[str, str]) -> None:
    body = json_body({"foo": "bar"})
    headers = {
        "Webhook-Signature": legacy_entry("event-name", body),
        "Webhook-Event": "event-name",
        "Webhook-Id": EVENT_ID,
        **rewritten,
    }

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(arriving(body, headers), WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_legacy_rejects_a_rewritten_body() -> None:
    signed = json_body({"total": 1})
    request = arriving(
        json_body({"total": 9}),
        {
            "Webhook-Signature": legacy_entry("event-name", signed),
            "Webhook-Event": "event-name",
            "Webhook-Id": EVENT_ID,
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(request, WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_legacy_requires_the_event_header() -> None:
    body = json_body({})
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
    with pytest.raises(InvalidArgumentError) as misconfigured:
        _ = RequestParser(algorithm="not-a-digest")

    assert str(misconfigured.value) == 'The signing algorithm "not-a-digest" is not available.'
