from __future__ import annotations

import copy

from xtr_mime import Email, RawMessage

from xtr_mailer import Envelope, SentMessage
from xtr_mailer.data_collector._mail_record import MailRecord
from xtr_mailer.event import MessageEvent


def _email() -> Email:
    return Email().from_("shop@example.com").to("customer@example.com").text("Hello")


def _record(queued: bool = False) -> MailRecord:
    email = _email()
    return MailRecord(MessageEvent(email, Envelope.create(email), "null://", queued=queued))


def test_an_email_announced_to_be_sent_now_is_pending() -> None:
    assert _record().status() == "pending"


def test_an_email_announced_to_be_queued_is_queued() -> None:
    assert _record(queued=True).status() == "queued"


def test_an_email_the_transport_took_is_sent() -> None:
    record = _record()
    record.sent = SentMessage(record.event.get_message(), record.event.get_envelope())

    assert record.status() == "sent"


def test_an_email_the_transport_refused_is_failed() -> None:
    record = _record()
    record.error = RuntimeError("down")

    assert record.status() == "failed"


def test_a_rejected_email_is_rejected_whatever_else_was_recorded() -> None:
    record = _record(queued=True)
    record.error = RuntimeError("down")
    record.event.reject()

    assert record.status() == "rejected"


def test_the_record_is_for_the_message_on_the_event_itself() -> None:
    record = _record()
    message = record.event.get_message()

    assert record.is_for(message)
    assert not record.is_for(copy.copy(message))


def test_the_record_follows_a_message_a_listener_replaced() -> None:
    record = _record()
    replaced = RawMessage(b"Subject: signed\r\n\r\nbody")
    record.event.set_message(replaced)

    assert record.is_for(replaced)


def test_the_message_announced_is_kept_after_a_listener_replaced_it() -> None:
    record = _record()
    announced = record.event.get_message()
    record.event.set_message(RawMessage(b"x"))

    assert record.original is announced
