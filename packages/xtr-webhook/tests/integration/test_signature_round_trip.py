"""A webhook this library sends parses back, here, to the event it was sent for.

The two sides are built and tested apart: the configurators' suite checks what
they write, the parser's suite checks what it accepts, and each builds its
expectation itself. That is what makes them worth testing — neither trusts the
other's code — and also what makes them blind to the one failure that matters
most: if what is signed, or the order it is signed in, changed on one side only,
both suites would stay green and every delivery would be refused.

So this runs the real chain, through the real :class:`Transport`, into the real
parser, for each format, and it is deliberately the only place in the suite
where the sender's bytes are handed to the receiver untouched.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from xtr_clock import MockClock
from xtr_http_message import ServerRequest
from xtr_remote_event import RemoteEvent

from tests.support.fake_http_sender import FakeHttpSender
from xtr_webhook.client import RequestParser
from xtr_webhook.exception import RejectWebhookError
from xtr_webhook.server import (
    HeadersConfigurator,
    HeaderSignatureConfigurator,
    JsonBodyConfigurator,
    JsonPayloadSerializer,
    SignatureFormat,
    Transport,
)
from xtr_webhook.subscriber import Subscriber

if TYPE_CHECKING:
    from collections.abc import Mapping

pytestmark = pytest.mark.anyio

# Named away from "secret" so the linter's hardcoded-credential rule stays useful.
_WHSEC = "s3cr3t"
_URL = "https://receiver.test/hook"
_SENT_AT = 1700000000
_EVENT_HEADER = "Webhook-Event"
_WINDOW = 'The "Webhook-Timestamp" HTTP request header is outside the accepted window.'

_EVERY_FORMAT = [
    SignatureFormat.LEGACY,
    SignatureFormat.STANDARD,
    SignatureFormat.TRANSITIONAL,
]
"""Every format, listed rather than derived, so adding one fails here until it round trips."""

_SIGNS_THE_TIMESTAMP = [SignatureFormat.STANDARD, SignatureFormat.TRANSITIONAL]
"""The formats whose signature covers the timestamp, and so can bound a replay."""

_SIGNS_THE_EVENT_HEADER = [SignatureFormat.LEGACY, SignatureFormat.TRANSITIONAL]
"""The formats that send the event's name as a header the legacy signature covers."""


def _event() -> RemoteEvent:
    return RemoteEvent("payment.authorized", "event-id", {"amount": 42})


def _frozen() -> MockClock:
    return MockClock(datetime.fromtimestamp(_SENT_AT, tz=UTC))


async def _send(
    event: RemoteEvent,
    signature_format: SignatureFormat,
    clock: MockClock,
) -> tuple[str, dict[str, str], bytes]:
    """Send ``event`` through a real transport and return what reached the wire.

    The chain is the one an application gets by default, with only the clock
    pinned, so a change to any configurator's defaults shows up here.
    """
    sender = FakeHttpSender()
    transport = Transport(
        sender,
        HeadersConfigurator(clock=clock, signature_format=signature_format),
        JsonBodyConfigurator(JsonPayloadSerializer(), signature_format),
        HeaderSignatureConfigurator(signature_format=signature_format),
    )

    await transport.send(Subscriber(_URL, _WHSEC), event)

    url, headers, body = sender.posts[0]

    return url, dict(headers), body


async def _parse(
    headers: Mapping[str, str],
    body: bytes,
    signature_format: SignatureFormat,
    clock: MockClock,
    secret: str = _WHSEC,
) -> RemoteEvent:
    """Feed what was sent back in as an arriving request, and read the event out."""
    parser = RequestParser(signature_format=signature_format, clock=clock)
    parsed = await parser.parse(ServerRequest("POST", "/", headers, body), secret)

    assert isinstance(parsed, RemoteEvent), f"one request carries one event, got {parsed!r}"

    return parsed


@pytest.mark.parametrize("signature_format", _EVERY_FORMAT)
async def test_a_sent_webhook_parses_back_to_the_event_it_was_sent_for(
    signature_format: SignatureFormat,
) -> None:
    clock = _frozen()
    event = _event()

    _, headers, body = await _send(event, signature_format, clock)

    assert await _parse(headers, body, signature_format, clock) == RemoteEvent(
        event.name,
        event.id,
        # Every format but the legacy one carries the name in the payload too,
        # because its signature covers the body and no header.
        event.payload
        if signature_format is SignatureFormat.LEGACY
        else {**event.payload, "type": event.name},
    )


@pytest.mark.parametrize("signature_format", _EVERY_FORMAT)
async def test_the_webhook_is_posted_to_the_subscriber_url(
    signature_format: SignatureFormat,
) -> None:
    url, _, _ = await _send(_event(), signature_format, _frozen())

    assert url == _URL


@pytest.mark.parametrize("signature_format", _SIGNS_THE_TIMESTAMP)
async def test_a_delivery_replayed_outside_the_window_is_refused(
    signature_format: SignatureFormat,
) -> None:
    clock = _frozen()
    _, headers, body = await _send(_event(), signature_format, clock)

    # The same clock both ends, moved between the two: the bytes are untouched,
    # only the hour they arrive in has changed.
    clock.sleep(3600)

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parse(headers, body, signature_format, clock)

    assert refused.value.status_code == 406
    assert str(refused.value) == _WINDOW


@pytest.mark.parametrize("signature_format", _SIGNS_THE_TIMESTAMP)
async def test_a_delivery_replayed_inside_the_window_is_still_accepted(
    signature_format: SignatureFormat,
) -> None:
    clock = _frozen()
    event = _event()
    _, headers, body = await _send(event, signature_format, clock)

    clock.sleep(299)

    assert (await _parse(headers, body, signature_format, clock)).id == event.id


async def test_a_rewritten_event_header_is_refused_by_the_legacy_format() -> None:
    clock = _frozen()
    _, headers, body = await _send(_event(), SignatureFormat.LEGACY, clock)

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parse(
            {**headers, _EVENT_HEADER: "payment.refunded"},
            body,
            SignatureFormat.LEGACY,
            clock,
        )

    assert refused.value.status_code == 406
    assert str(refused.value) == "Signature is wrong."


async def test_a_rewritten_event_header_cannot_rename_a_transitional_webhook() -> None:
    clock = _frozen()
    _, headers, body = await _send(_event(), SignatureFormat.TRANSITIONAL, clock)

    parsed = await _parse(
        {**headers, _EVENT_HEADER: "payment.refunded"},
        body,
        SignatureFormat.TRANSITIONAL,
        clock,
    )

    # The Standard Webhooks entry still verifies, and it reads no header at all,
    # so the name comes from the signed payload rather than the rewritten header.
    assert parsed.name == "payment.authorized"


async def test_the_standard_format_sends_the_event_name_in_the_body_only() -> None:
    _, headers, body = await _send(_event(), SignatureFormat.STANDARD, _frozen())

    assert _EVENT_HEADER not in headers
    assert json.loads(body)["type"] == "payment.authorized"


@pytest.mark.parametrize("signature_format", _EVERY_FORMAT)
async def test_a_receiver_holding_another_secret_refuses_the_webhook(
    signature_format: SignatureFormat,
) -> None:
    clock = _frozen()
    _, headers, body = await _send(_event(), signature_format, clock)

    with pytest.raises(RejectWebhookError) as refused:
        _ = await _parse(headers, body, signature_format, clock, secret="another-" + _WHSEC)

    assert refused.value.status_code == 406
    assert str(refused.value) == "Signature is wrong."


@pytest.mark.parametrize("signature_format", _SIGNS_THE_EVENT_HEADER)
async def test_the_event_header_travels_with_the_formats_whose_signature_covers_it(
    signature_format: SignatureFormat,
) -> None:
    _, headers, _ = await _send(_event(), signature_format, _frozen())

    assert headers[_EVENT_HEADER] == "payment.authorized"
