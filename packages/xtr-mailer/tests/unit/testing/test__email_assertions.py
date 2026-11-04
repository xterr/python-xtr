"""Checks on the emails an application sent or queued, read from what a listener recorded."""

from __future__ import annotations

import re

import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_mime import Address, Email

from xtr_mailer import Envelope
from xtr_mailer.event import MessageEvent, MessageEvents
from xtr_mailer.event_listener import MessageLoggerListener
from xtr_mailer.testing import (
    assert_email_count,
    assert_email_is_not_queued,
    assert_email_is_queued,
    assert_queued_email_count,
)
from xtr_mailer.transport import NullTransport


def _event(transport_name: str, *, queued: bool = False) -> MessageEvent:
    email = Email().from_("sender@example.com").to("recipient@example.com").text("Hello")
    envelope = Envelope(Address("sender@example.com"), [Address("recipient@example.com")])
    return MessageEvent(email, envelope, transport_name, queued=queued)


def _record(*events: MessageEvent) -> MessageEvents:
    recorded = MessageEvents()
    for event in events:
        recorded.add(event)
    return recorded


def _events() -> MessageEvents:
    """Two emails sent through ``null://`` and one queued for it, one sent through SMTP."""
    return _record(
        _event("null://"),
        _event("null://", queued=True),
        _event("null://"),
        _event("smtp://localhost"),
    )


def _failure(message: str) -> pytest.RaisesExc[AssertionError]:
    return pytest.raises(AssertionError, match=f"^{re.escape(message)}$")


def test_the_emails_sent_are_counted_whatever_their_transport() -> None:
    assert_email_count(_events(), 3)


def test_the_emails_sent_through_one_transport_are_counted() -> None:
    assert_email_count(_events(), 2, "null://")


def test_another_count_of_emails_sent_fails_the_check() -> None:
    with _failure('Failed asserting that the Transport has sent "1" emails (3 sent).'):
        assert_email_count(_events(), 1)


def test_a_failed_count_on_one_transport_names_it() -> None:
    with _failure('Failed asserting that the Transport null:// has sent "1" emails (2 sent).'):
        assert_email_count(_events(), 1, "null://")


def test_the_emails_queued_are_counted() -> None:
    assert_queued_email_count(_events(), 1)


def test_the_emails_queued_for_one_transport_are_counted() -> None:
    assert_queued_email_count(_events(), 0, "smtp://localhost")


def test_another_count_of_emails_queued_fails_the_check() -> None:
    with _failure('Failed asserting that the Transport null:// has queued "2" emails (1 queued).'):
        assert_queued_email_count(_events(), 2, "null://")


def test_a_transport_named_0_is_named_in_a_failed_count() -> None:
    with _failure('Failed asserting that the Transport 0 has sent "2" emails (1 sent).'):
        assert_email_count(_record(_event("0"), _event("main")), 2, "0")


def test_a_queued_email_passes_the_queued_check() -> None:
    assert_email_is_queued(_event("null://", queued=True))


def test_an_email_sent_fails_the_queued_check() -> None:
    with _failure("Failed asserting that the Email is queued."):
        assert_email_is_queued(_event("null://"))


def test_an_email_sent_passes_the_not_queued_check() -> None:
    assert_email_is_not_queued(_event("null://"))


def test_a_queued_email_fails_the_not_queued_check() -> None:
    with _failure("Failed asserting that the Email is not queued."):
        assert_email_is_not_queued(_event("null://", queued=True))


@pytest.mark.anyio
async def test_the_checks_read_what_a_message_logger_recorded() -> None:
    dispatcher = EventDispatcher()
    listener = MessageLoggerListener()
    dispatcher.add_listener(MessageEvent, listener.on_message, MessageLoggerListener.PRIORITY)
    email = Email().from_("sender@example.com").to("recipient@example.com").text("Hello")

    _ = await NullTransport(dispatcher).send(email)

    assert_email_count(listener.get_events(), 1, "null://")
