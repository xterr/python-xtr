"""The emails seen so far, by transport, an email queued then sent in one process seen once."""

from __future__ import annotations

from xtr_mime import Address, Email

from xtr_mailer import Envelope
from xtr_mailer.event import MessageEvent, MessageEvents


def _event(subject: str, transport: str = "main", *, queued: bool = False) -> MessageEvent:
    email = Email().from_("sender@example.com").to("recipient@example.com").subject(subject)
    envelope = Envelope(Address("sender@example.com"), [Address("recipient@example.com")])
    return MessageEvent(email.text("Hello"), envelope, transport, queued=queued)


def _record(*events: MessageEvent) -> MessageEvents:
    recorded = MessageEvents()
    for event in events:
        recorded.add(event)
    return recorded


def test_it_starts_empty() -> None:
    events = MessageEvents()

    assert events.get_events() == []
    assert events.get_messages() == []
    assert events.get_transports() == []


def test_it_lists_every_event_in_order() -> None:
    first, second = _event("First"), _event("Second", queued=True)

    assert _record(first, second).get_events() == [first, second]


def test_it_lists_each_transport_once_in_the_order_first_seen() -> None:
    events = _record(_event("A", "smtp"), _event("B", "api"), _event("C", "smtp"))

    assert events.get_transports() == ["smtp", "api"]


def test_it_filters_events_by_transport() -> None:
    smtp, api, smtp_again = _event("A", "smtp"), _event("B", "api"), _event("C", "smtp")
    events = _record(smtp, api, smtp_again)

    assert events.get_events("smtp") == [smtp, smtp_again]
    assert events.get_events("other") == []


def test_it_filters_messages_by_transport() -> None:
    smtp, api = _event("A", "smtp"), _event("B", "api")

    assert _record(smtp, api).get_messages("api") == [api.get_message()]


def test_a_message_queued_then_sent_in_the_same_process_is_reported_once() -> None:
    # What a synchronous bus records: each email queued, then sent by its handler.
    first_queued, first_sent = _event("First", queued=True), _event("First")
    second_queued, second_sent = _event("Second", queued=True), _event("Second")
    events = _record(first_queued, first_sent, second_queued, second_sent)

    assert len(events.get_events()) == 4
    assert events.get_messages() == [first_sent.get_message(), second_sent.get_message()]


def test_a_message_left_in_the_queue_is_still_reported() -> None:
    first, second = _event("First", queued=True), _event("Second", queued=True)
    events = _record(first, second)

    assert len(events.get_events()) == 2
    assert events.get_messages() == [first.get_message(), second.get_message()]


def test_a_queued_message_is_kept_when_an_email_was_sent_before() -> None:
    sent, queued = _event("Sent"), _event("Queued", queued=True)

    assert _record(sent, queued).get_messages() == [sent.get_message(), queued.get_message()]
