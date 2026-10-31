"""The parser under the Standard Webhooks signature, alone and beside the legacy one."""

from __future__ import annotations

import base64
from datetime import UTC, datetime

import pytest
from xtr_clock import Clock, MockClock
from xtr_remote_event import RemoteEvent
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

from tests.support.signed_requests import (
    EVENT_ID,
    WHSEC,
    arriving,
    event_body,
    legacy_entry,
    standard_entry,
)
from xtr_webhook.client import RequestParser
from xtr_webhook.exception import RejectWebhookError
from xtr_webhook.server.signature_format import SignatureFormat

_NOW = 1700000000
_WINDOW = 'The "Webhook-Timestamp" HTTP request header is outside the accepted window.'
_EVENT = RemoteEvent("event-name", EVENT_ID, {})


def _frozen() -> MockClock:
    return MockClock(datetime.fromtimestamp(_NOW, tz=UTC))


def _parser(
    signature_format: SignatureFormat | str = SignatureFormat.STANDARD,
    tolerance: int = 300,
    clock: MockClock | None = None,
) -> RequestParser:
    return RequestParser(
        Serializer([PydanticNormalizer()], [JsonEncoder()]),
        signature_format=signature_format,
        timestamp_tolerance=tolerance,
        clock=clock if clock is not None else _frozen(),
    )


def _stamped(timestamp: int | str, signature: str | None = None) -> dict[str, str]:
    body = event_body()
    return {
        "Webhook-Signature": signature or standard_entry(timestamp, body),
        "Webhook-Id": EVENT_ID,
        "Webhook-Timestamp": str(timestamp),
    }


@pytest.mark.anyio
async def test_standard_reads_the_event_the_signed_body_holds() -> None:
    parsed = await _parser().parse(arriving(event_body(), _stamped(_NOW)), WHSEC)

    assert parsed == _EVENT


@pytest.mark.anyio
async def test_standard_rejects_a_foreign_signature() -> None:
    forged = standard_entry(_NOW, event_body(), key=b"wrong-value")

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(arriving(event_body(), _stamped(_NOW, forged)), WHSEC)

    assert str(refused.value) == "Signature is wrong."


@pytest.mark.anyio
async def test_standard_ignores_a_forged_event_header() -> None:
    headers = {**_stamped(_NOW), "Webhook-Event": "payment.refunded"}

    parsed = await _parser().parse(arriving(event_body(), headers), WHSEC)

    assert parsed == _EVENT


@pytest.mark.anyio
async def test_legacy_ignores_a_standard_entry() -> None:
    headers = {**_stamped(_NOW), "Webhook-Event": "event-name"}

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser(SignatureFormat.LEGACY).parse(arriving(event_body(), headers), WHSEC)

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
        _ = await _parser().parse(arriving(event_body(), _stamped(timestamp)), WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == _WINDOW


@pytest.mark.anyio
async def test_a_tolerance_of_zero_accepts_any_timestamp() -> None:
    request = arriving(event_body(), _stamped(_NOW - 86400))

    assert await _parser(tolerance=0).parse(request, WHSEC) == _EVENT


@pytest.mark.anyio
async def test_standard_requires_the_timestamp_header() -> None:
    headers = {"Webhook-Signature": standard_entry(_NOW, event_body()), "Webhook-Id": EVENT_ID}

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser().parse(arriving(event_body(), headers), WHSEC)

    assert str(refused.value) == 'Missing "Webhook-Timestamp" HTTP request signature header.'


@pytest.mark.anyio
async def test_standard_uses_the_decoded_whsec_secret() -> None:
    # The peer signs with the decoded bytes, as every Standard Webhooks sender does.
    signature = standard_entry(_NOW, event_body(), key=b"raw-key-bytes")
    whsec = "whsec_" + base64.b64encode(b"raw-key-bytes").decode()

    parsed = await _parser().parse(arriving(event_body(), _stamped(_NOW, signature)), whsec)

    assert parsed == _EVENT


@pytest.mark.anyio
async def test_any_of_several_entries_is_enough_during_a_rotation() -> None:
    stale = standard_entry(_NOW, event_body(), key=b"old-value")
    entries = stale + "  " + standard_entry(_NOW, event_body())

    parsed = await _parser().parse(arriving(event_body(), _stamped(_NOW, entries)), WHSEC)

    assert parsed == _EVENT


@pytest.mark.anyio
async def test_transitional_accepts_a_legacy_only_sender() -> None:
    headers = {
        "Webhook-Signature": legacy_entry("event-name", event_body()),
        "Webhook-Event": "event-name",
        "Webhook-Id": EVENT_ID,
    }

    parsed = await _parser(SignatureFormat.TRANSITIONAL).parse(
        arriving(event_body(), headers), WHSEC
    )

    assert parsed == _EVENT


@pytest.mark.anyio
async def test_transitional_accepts_a_standard_only_sender() -> None:
    request = arriving(event_body(), _stamped(_NOW))

    assert await _parser(SignatureFormat.TRANSITIONAL).parse(request, WHSEC) == _EVENT


@pytest.mark.anyio
async def test_transitional_bounds_replays_whatever_the_entry_order() -> None:
    legacy = legacy_entry("event-name", event_body())
    standard = standard_entry(_NOW - 3600, event_body())

    for signature in (legacy + " " + standard, standard + " " + legacy):
        headers = {**_stamped(_NOW - 3600, signature), "Webhook-Event": "event-name"}

        with pytest.raises(RejectWebhookError) as refused:
            _ = await _parser(SignatureFormat.TRANSITIONAL).parse(
                arriving(event_body(), headers), WHSEC
            )

        assert str(refused.value) == _WINDOW


@pytest.mark.anyio
async def test_a_timestamp_at_the_edge_of_the_window_is_accepted() -> None:
    clock = _frozen()
    clock.sleep(300)

    parsed = await _parser(clock=clock).parse(arriving(event_body(), _stamped(_NOW)), WHSEC)

    assert parsed == _EVENT


@pytest.mark.anyio
async def test_a_timestamp_just_past_the_window_is_refused() -> None:
    clock = _frozen()
    clock.sleep(301)

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parser(clock=clock).parse(arriving(event_body(), _stamped(_NOW)), WHSEC)

    assert str(refused.value) == _WINDOW


@pytest.mark.anyio
async def test_it_reads_the_clock_in_force_when_handed_none() -> None:
    parser = RequestParser(
        Serializer([PydanticNormalizer()], [JsonEncoder()]),
        signature_format=SignatureFormat.STANDARD,
    )

    with Clock.using(_frozen()):
        parsed = await parser.parse(arriving(event_body(), _stamped(_NOW)), WHSEC)

    assert parsed == _EVENT


@pytest.mark.anyio
async def test_the_signature_format_may_arrive_as_its_string() -> None:
    parsed = await _parser("standard").parse(arriving(event_body(), _stamped(_NOW)), WHSEC)

    assert parsed == _EVENT
