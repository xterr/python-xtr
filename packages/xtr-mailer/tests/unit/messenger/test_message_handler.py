"""The handler the bus hands a queued email to, which sends it through the transport.

Upstream's one case turns a rate-limited send into a recoverable error carrying the delay.
Adapted (D11): there is no recoverable-with-delay error here, so the limiter's own error goes
through as it was raised, and the bus transport's retry policy decides what to do with it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from xtr_mime import Address, Email, RawMessage
from xtr_rate_limiter import RateLimit, RateLimitExceededError

from tests.support.scripted_transport import ScriptedTransport
from xtr_mailer import Envelope
from xtr_mailer.messenger import MessageHandler, SendEmailMessage

pytestmark = pytest.mark.anyio


def _envelope() -> Envelope:
    return Envelope(Address("fabien@example.com"), [Address("helene@example.com")])


async def test_the_email_is_sent_with_the_envelope_it_was_queued_with() -> None:
    transport = ScriptedTransport("fake://")
    message, envelope = RawMessage(""), _envelope()

    sent = await MessageHandler(transport)(SendEmailMessage(message, envelope))

    assert sent is not None
    assert transport.received == [message]
    assert sent.get_envelope() is envelope


async def test_without_an_envelope_the_one_the_headers_give_is_used() -> None:
    transport = ScriptedTransport("fake://")
    email = Email().from_("fabien@example.com").to("helene@example.com").text("Hi")

    sent = await MessageHandler(transport)(SendEmailMessage(email))

    assert sent is not None
    assert [a.get_address() for a in sent.get_envelope().get_recipients()] == ["helene@example.com"]


async def test_a_rate_limited_send_raises_the_limiters_error_as_it_was_raised() -> None:
    limit = RateLimit(0, datetime(2026, 11, 3, 12, 0, 30, tzinfo=UTC), accepted=False, limit=2)
    refused = RateLimitExceededError(limit)
    handler = MessageHandler(ScriptedTransport("fake://", [refused]))

    with pytest.raises(RateLimitExceededError) as caught:
        _ = await handler(SendEmailMessage(RawMessage(""), _envelope()))

    assert caught.value is refused
