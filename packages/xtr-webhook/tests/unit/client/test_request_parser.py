from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime

import pytest
from xtr_clock import Clock, MockClock
from xtr_http_message import ServerRequest
from xtr_remote_event import RemoteEvent

from xtr_webhook.client import RequestParser
from xtr_webhook.exception import InvalidArgumentError, RejectWebhookError
from xtr_webhook.server.signature_format import SignatureFormat

# Named away from "secret" so the linter's hardcoded-credential rule stays useful.
_WHSEC = "s3cr3t"
_WHSEC_KEY = _WHSEC.encode()
_NOW = 1700000000
_WINDOW = 'The "Webhook-Timestamp" HTTP request header is outside the accepted window.'


def _legacy(event: str, body: bytes, key: str = _WHSEC) -> str:
    """A legacy entry, built with hmac directly so it does not trust the code under test."""
    digest = hmac.new(key.encode(), event.encode() + b"event-id" + body, hashlib.sha256)

    return "sha256=" + digest.hexdigest()


def _standard(timestamp: int | str, body: bytes, key: bytes = _WHSEC_KEY) -> str:
    """A Standard Webhooks entry, built with hmac and base64 directly for the same reason."""
    digest = hmac.new(key, f"event-id.{timestamp}.".encode() + body, hashlib.sha256)

    return "v1," + base64.b64encode(digest.digest()).decode()


def _request(body: bytes, headers: dict[str, str] | None = None) -> ServerRequest:
    return ServerRequest("POST", "/", {"Content-Type": "application/json", **(headers or {})}, body)


def _frozen() -> MockClock:
    return MockClock(datetime.fromtimestamp(_NOW, tz=UTC))


def _parser(
    signature_format: SignatureFormat = SignatureFormat.LEGACY,
    tolerance: int = 300,
    clock: MockClock | None = None,
) -> RequestParser:
    return RequestParser(
        signature_format=signature_format,
        timestamp_tolerance=tolerance,
        clock=clock if clock is not None else _frozen(),
    )


@pytest.mark.anyio
async def test_it_refuses_a_request_its_matcher_does_not_claim() -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(ServerRequest("GET", "/"), _WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == "Request does not match."


@pytest.mark.anyio
async def test_it_refuses_a_json_body_that_is_not_an_object() -> None:
    body = b"1"
    request = _request(
        body,
        {
            "Webhook-Signature": _legacy("event-name", body),
            "Webhook-Event": "event-name",
            "Webhook-Id": "event-id",
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(request, _WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == "Request body is malformed."


@pytest.mark.anyio
async def test_a_wrong_signature_is_answered_before_the_body_is_decoded() -> None:
    body = b"{not json at all"
    request = _request(
        body,
        {
            "Webhook-Signature": _legacy("event-name", body, key="wrong-value"),
            "Webhook-Event": "event-name",
            "Webhook-Id": "event-id",
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(request, _WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_a_body_that_will_not_decode_is_still_malformed_once_it_is_genuine() -> None:
    body = b"{not json at all"
    request = _request(
        body,
        {
            "Webhook-Signature": _legacy("event-name", body),
            "Webhook-Event": "event-name",
            "Webhook-Id": "event-id",
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(request, _WHSEC)

    assert str(refused.value) == "Request body is malformed."


@pytest.mark.anyio
async def test_legacy_accepts_its_own_signature() -> None:
    body = b'{"foo":"bar"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _legacy("event-name", body),
            "Webhook-Event": "event-name",
            "Webhook-Id": "event-id",
        },
    )

    parsed = await _parser().parse(request, _WHSEC)

    assert parsed == RemoteEvent("event-name", "event-id", {"foo": "bar"})


@pytest.mark.anyio
async def test_legacy_rejects_a_foreign_signature() -> None:
    body = b'{"foo":"bar"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _legacy("event-name", body, key="wrong-value"),
            "Webhook-Event": "event-name",
            "Webhook-Id": "event-id",
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(request, _WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_legacy_rejects_a_rewritten_event_header() -> None:
    body = b'{"foo":"bar"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _legacy("event-name", body),
            "Webhook-Event": "rewritten-name",
            "Webhook-Id": "event-id",
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(request, _WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_legacy_ignores_a_standard_entry() -> None:
    body = b'{"type":"event-name"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW, body),
            "Webhook-Event": "event-name",
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW),
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(request, _WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_legacy_requires_the_event_header() -> None:
    body = b'{"foo":"bar"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _legacy("event-name", body),
            "Webhook-Id": "event-id",
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(request, _WHSEC)

    assert str(refused.value) == 'Missing "Webhook-Event" HTTP request signature header.'


@pytest.mark.anyio
async def test_standard_reads_the_event_name_from_the_payload() -> None:
    body = b'{"type":"payment.authorized","amount":42}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW, body),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW),
        },
    )

    parsed = await _parser(SignatureFormat.STANDARD).parse(request, _WHSEC)

    assert parsed == RemoteEvent(
        "payment.authorized", "event-id", {"type": "payment.authorized", "amount": 42}
    )


@pytest.mark.anyio
async def test_standard_rejects_a_foreign_signature() -> None:
    body = b'{"type":"event-name"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW, body, key=b"wrong-value"),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW),
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser(SignatureFormat.STANDARD).parse(request, _WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_standard_rejects_a_payload_without_a_type() -> None:
    body = b'{"amount":42}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW, body),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW),
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser(SignatureFormat.STANDARD).parse(request, _WHSEC)

    assert str(refused.value) == 'The payload is missing the "type" key holding the event name.'


@pytest.mark.anyio
async def test_standard_ignores_a_forged_event_header() -> None:
    body = b'{"type":"payment.authorized"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW, body),
            "Webhook-Event": "payment.refunded",
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW),
        },
    )

    parsed = await _parser(SignatureFormat.STANDARD).parse(request, _WHSEC)

    assert parsed == RemoteEvent("payment.authorized", "event-id", {"type": "payment.authorized"})


@pytest.mark.anyio
async def test_standard_rejects_a_replay_outside_the_tolerance() -> None:
    body = b'{"type":"event-name"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW - 3600, body),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW - 3600),
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser(SignatureFormat.STANDARD).parse(request, _WHSEC)

    assert str(refused.value) == _WINDOW


@pytest.mark.anyio
async def test_standard_rejects_a_non_numeric_timestamp() -> None:
    body = b'{"type":"event-name"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard("not-a-number", body),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": "not-a-number",
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser(SignatureFormat.STANDARD).parse(request, _WHSEC)

    assert str(refused.value) == _WINDOW


@pytest.mark.anyio
async def test_standard_refuses_a_timestamp_too_long_to_read_as_a_number() -> None:
    body = b'{"type":"event-name"}'
    # Longer than the runtime converts a digit string to an int, so reading it would
    # raise where the sender is owed a refusal.
    timestamp = "9" * 5000
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(timestamp, body),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": timestamp,
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser(SignatureFormat.STANDARD).parse(request, _WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == _WINDOW


@pytest.mark.anyio
async def test_a_tolerance_of_zero_accepts_any_timestamp() -> None:
    body = b'{"type":"event-name"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW - 86400, body),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW - 86400),
        },
    )

    parsed = await _parser(SignatureFormat.STANDARD, tolerance=0).parse(request, _WHSEC)

    assert parsed == RemoteEvent("event-name", "event-id", {"type": "event-name"})


@pytest.mark.anyio
async def test_standard_requires_the_timestamp_header() -> None:
    body = b'{"type":"event-name"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW, body),
            "Webhook-Id": "event-id",
        },
    )

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser(SignatureFormat.STANDARD).parse(request, _WHSEC)

    assert str(refused.value) == 'Missing "Webhook-Timestamp" HTTP request signature header.'


@pytest.mark.anyio
async def test_standard_uses_the_decoded_whsec_secret() -> None:
    body = b'{"type":"event-name"}'
    # The peer signs with the decoded bytes, as every Standard Webhooks sender does.
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW, body, key=b"raw-key-bytes"),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW),
        },
    )

    parsed = await _parser(SignatureFormat.STANDARD).parse(
        request, "whsec_" + base64.b64encode(b"raw-key-bytes").decode()
    )

    assert parsed == RemoteEvent("event-name", "event-id", {"type": "event-name"})


@pytest.mark.anyio
async def test_any_of_several_entries_is_enough_during_a_rotation() -> None:
    body = b'{"type":"event-name"}'
    stale = _standard(_NOW, body, key=b"old-value")
    request = _request(
        body,
        {
            "Webhook-Signature": stale + "  " + _standard(_NOW, body),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW),
        },
    )

    parsed = await _parser(SignatureFormat.STANDARD).parse(request, _WHSEC)

    assert parsed == RemoteEvent("event-name", "event-id", {"type": "event-name"})


@pytest.mark.anyio
async def test_transitional_accepts_a_legacy_only_sender() -> None:
    body = b'{"foo":"bar"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _legacy("event-name", body),
            "Webhook-Event": "event-name",
            "Webhook-Id": "event-id",
        },
    )

    parsed = await _parser(SignatureFormat.TRANSITIONAL).parse(request, _WHSEC)

    assert parsed == RemoteEvent("event-name", "event-id", {"foo": "bar"})


@pytest.mark.anyio
async def test_transitional_accepts_a_standard_only_sender() -> None:
    body = b'{"type":"event-name"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW, body),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW),
        },
    )

    parsed = await _parser(SignatureFormat.TRANSITIONAL).parse(request, _WHSEC)

    assert parsed == RemoteEvent("event-name", "event-id", {"type": "event-name"})


@pytest.mark.anyio
async def test_transitional_bounds_replays_whatever_the_entry_order() -> None:
    body = b'{"type":"event-name"}'
    legacy = _legacy("event-name", body)
    standard = _standard(_NOW - 3600, body)

    for signature in (legacy + " " + standard, standard + " " + legacy):
        request = _request(
            body,
            {
                "Webhook-Signature": signature,
                "Webhook-Event": "event-name",
                "Webhook-Id": "event-id",
                "Webhook-Timestamp": str(_NOW - 3600),
            },
        )

        with pytest.raises(RejectWebhookError) as refused:
            _ = await _parser(SignatureFormat.TRANSITIONAL).parse(request, _WHSEC)

        assert str(refused.value) == _WINDOW


@pytest.mark.anyio
async def test_an_empty_secret_is_a_misconfiguration_not_a_refusal() -> None:
    with pytest.raises(InvalidArgumentError) as misconfigured:
        _ = await _parser().parse(_request(b"{}"), "")

    assert str(misconfigured.value) == "A non-empty secret is required."


@pytest.mark.anyio
async def test_a_timestamp_at_the_edge_of_the_window_is_accepted() -> None:
    body = b'{"type":"event-name"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW, body),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW),
        },
    )
    clock = _frozen()
    clock.sleep(300)

    parsed = await _parser(SignatureFormat.STANDARD, clock=clock).parse(request, _WHSEC)

    assert parsed == RemoteEvent("event-name", "event-id", {"type": "event-name"})


@pytest.mark.anyio
async def test_a_timestamp_just_past_the_window_is_refused() -> None:
    body = b'{"type":"event-name"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW, body),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW),
        },
    )
    clock = _frozen()
    clock.sleep(301)

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser(SignatureFormat.STANDARD, clock=clock).parse(request, _WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == _WINDOW


@pytest.mark.anyio
async def test_it_reads_the_clock_in_force_when_handed_none() -> None:
    body = b'{"type":"event-name"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW, body),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW),
        },
    )

    with Clock.using(_frozen()):
        parsed = await RequestParser(signature_format=SignatureFormat.STANDARD).parse(
            request, _WHSEC
        )

    assert parsed == RemoteEvent("event-name", "event-id", {"type": "event-name"})


@pytest.mark.anyio
async def test_the_signature_format_may_arrive_as_its_string() -> None:
    body = b'{"type":"event-name"}'
    request = _request(
        body,
        {
            "Webhook-Signature": _standard(_NOW, body),
            "Webhook-Id": "event-id",
            "Webhook-Timestamp": str(_NOW),
        },
    )

    parser = RequestParser(signature_format="standard", clock=_frozen())

    assert await parser.parse(request, _WHSEC) == RemoteEvent(
        "event-name", "event-id", {"type": "event-name"}
    )


def test_an_algorithm_this_runtime_cannot_make_is_refused_where_it_is_configured() -> None:
    with pytest.raises(InvalidArgumentError) as misconfigured:
        _ = RequestParser(algorithm="not-a-digest")

    assert str(misconfigured.value) == 'The signing algorithm "not-a-digest" is not available.'
