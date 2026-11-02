"""The parser under the Standard Webhooks signature, alone and beside the legacy one."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import pytest
from xtr_clock import Clock, MockClock
from xtr_remote_event import RemoteEvent

from tests.support.signed_requests import (
    EVENT_ID,
    WHSEC,
    arriving,
    json_body,
    legacy_entry,
    standard_entry,
)
from xtr_webhook.client import RequestParser
from xtr_webhook.exception import RejectWebhookError
from xtr_webhook.server.signature_format import SignatureFormat

_NOW = 1700000000
_WINDOW = 'The "Webhook-Timestamp" HTTP request header is outside the accepted window.'
_PAYLOAD: dict[str, object] = {"type": "event-name", "lines": [{"qty": 2}], "note": None}
_BODY = json_body(_PAYLOAD)
_EVENT = RemoteEvent("event-name", EVENT_ID, _PAYLOAD)


def _frozen() -> MockClock:
    return MockClock(datetime.fromtimestamp(_NOW, tz=UTC))


def _parser(
    signature_format: SignatureFormat | str = SignatureFormat.STANDARD,
    tolerance: int = 300,
    clock: MockClock | None = None,
) -> RequestParser:
    return RequestParser(
        signature_format=signature_format,
        timestamp_tolerance=tolerance,
        clock=clock if clock is not None else _frozen(),
    )


def _stamped(
    timestamp: int | str, signature: str | None = None, body: bytes = _BODY
) -> dict[str, str]:
    return {
        "Webhook-Signature": signature or standard_entry(timestamp, body),
        "Webhook-Id": EVENT_ID,
        "Webhook-Timestamp": str(timestamp),
    }


@pytest.mark.anyio
async def test_standard_reads_the_event_name_from_the_payload() -> None:
    parsed = await _parser().parse(arriving(_BODY, _stamped(_NOW)), WHSEC)

    assert parsed == _EVENT
    assert type(parsed) is RemoteEvent


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload", [{"amount": 42}, {"type": 7}], ids=["no-type", "a-type-that-is-no-string"]
)
async def test_standard_rejects_a_payload_naming_no_event(payload: dict[str, object]) -> None:
    body = json_body(payload)

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(arriving(body, _stamped(_NOW, body=body)), WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == 'The payload is missing the "type" key holding the event name.'


@pytest.mark.anyio
@pytest.mark.parametrize(
    "rewritten",
    [{"Webhook-Id": "rewritten-id"}, {"Webhook-Timestamp": str(_NOW + 1)}],
    ids=["id", "timestamp"],
)
async def test_standard_rejects_a_rewritten_header(rewritten: dict[str, str]) -> None:
    headers = {**_stamped(_NOW), **rewritten}

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(arriving(_BODY, headers), WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_standard_rejects_a_rewritten_body() -> None:
    rewritten = json_body({**_PAYLOAD, "type": "payment.refunded"})

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(arriving(rewritten, _stamped(_NOW)), WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_standard_rejects_a_foreign_signature() -> None:
    forged = standard_entry(_NOW, _BODY, key=b"wrong-value")

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(arriving(_BODY, _stamped(_NOW, forged)), WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_standard_ignores_a_forged_event_header() -> None:
    headers = {**_stamped(_NOW), "Webhook-Event": "payment.refunded"}

    parsed = await _parser().parse(arriving(_BODY, headers), WHSEC)

    assert parsed == _EVENT


@pytest.mark.anyio
async def test_legacy_ignores_a_standard_entry() -> None:
    headers = {**_stamped(_NOW), "Webhook-Event": "event-name"}

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser(SignatureFormat.LEGACY).parse(arriving(_BODY, headers), WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
@pytest.mark.parametrize(
    "timestamp",
    [_NOW - 3600, "not-a-number", "9" * 5000],
    ids=["an-hour-ago", "not-a-number", "too-long-to-read"],
)
async def test_standard_refuses_a_timestamp_it_cannot_hold_to_the_window(
    timestamp: int | str,
) -> None:
    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(arriving(_BODY, _stamped(timestamp)), WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == _WINDOW


@pytest.mark.anyio
async def test_a_tolerance_of_zero_accepts_any_timestamp() -> None:
    request = arriving(_BODY, _stamped(_NOW - 86400))

    assert await _parser(tolerance=0).parse(request, WHSEC) == _EVENT


@pytest.mark.anyio
async def test_standard_requires_the_timestamp_header() -> None:
    headers = {"Webhook-Signature": standard_entry(_NOW, _BODY), "Webhook-Id": EVENT_ID}

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(arriving(_BODY, headers), WHSEC)

    assert str(refused.value) == 'Missing "Webhook-Timestamp" HTTP request signature header.'


@pytest.mark.anyio
async def test_standard_uses_the_decoded_whsec_secret() -> None:
    # The peer signs with the decoded bytes, as every Standard Webhooks sender does.
    signature = standard_entry(_NOW, _BODY, key=b"raw-key-bytes")
    whsec = "whsec_" + base64.b64encode(b"raw-key-bytes").decode()

    parsed = await _parser().parse(arriving(_BODY, _stamped(_NOW, signature)), whsec)

    assert parsed == _EVENT


@pytest.mark.anyio
async def test_any_of_several_entries_is_enough_during_a_rotation() -> None:
    stale = standard_entry(_NOW, _BODY, key=b"old-value")
    entries = stale + "  " + standard_entry(_NOW, _BODY)

    parsed = await _parser().parse(arriving(_BODY, _stamped(_NOW, entries)), WHSEC)

    assert parsed == _EVENT


@pytest.mark.anyio
async def test_transitional_accepts_a_legacy_only_sender() -> None:
    body = json_body({"total": 1})
    headers = {
        "Webhook-Signature": legacy_entry("event-name", body),
        "Webhook-Event": "event-name",
        "Webhook-Id": EVENT_ID,
    }

    parsed = await _parser(SignatureFormat.TRANSITIONAL).parse(arriving(body, headers), WHSEC)

    assert parsed == RemoteEvent("event-name", EVENT_ID, {"total": 1})


@pytest.mark.anyio
async def test_transitional_accepts_a_standard_only_sender() -> None:
    request = arriving(_BODY, _stamped(_NOW))

    assert await _parser(SignatureFormat.TRANSITIONAL).parse(request, WHSEC) == _EVENT


@pytest.mark.anyio
async def test_transitional_bounds_replays_whatever_the_entry_order() -> None:
    legacy = legacy_entry("event-name", _BODY)
    standard = standard_entry(_NOW - 3600, _BODY)

    for signature in (legacy + " " + standard, standard + " " + legacy):
        headers = {**_stamped(_NOW - 3600, signature), "Webhook-Event": "event-name"}

        with pytest.raises(RejectWebhookError) as refused:
            _ = await _parser(SignatureFormat.TRANSITIONAL).parse(arriving(_BODY, headers), WHSEC)

        assert str(refused.value) == _WINDOW


@pytest.mark.anyio
async def test_a_timestamp_at_the_edge_of_the_window_is_accepted() -> None:
    clock = _frozen()
    clock.sleep(300)

    parsed = await _parser(clock=clock).parse(arriving(_BODY, _stamped(_NOW)), WHSEC)

    assert parsed == _EVENT


@pytest.mark.anyio
async def test_a_timestamp_just_past_the_window_is_refused() -> None:
    clock = _frozen()
    clock.sleep(301)

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser(clock=clock).parse(arriving(_BODY, _stamped(_NOW)), WHSEC)

    assert str(refused.value) == _WINDOW


@pytest.mark.anyio
async def test_it_reads_the_clock_in_force_when_handed_none() -> None:
    parser = RequestParser(signature_format=SignatureFormat.STANDARD)

    with Clock.using(_frozen()):
        parsed = await parser.parse(arriving(_BODY, _stamped(_NOW)), WHSEC)

    assert parsed == _EVENT


@pytest.mark.anyio
async def test_the_signature_format_may_arrive_as_its_string() -> None:
    parsed = await _parser("standard").parse(arriving(_BODY, _stamped(_NOW)), WHSEC)

    assert parsed == _EVENT
