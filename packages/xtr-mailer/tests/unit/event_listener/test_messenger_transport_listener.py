"""The listener routing a queued email to the message bus transports its header names."""

from __future__ import annotations

from xtr_messenger.stamp import TransportNamesStamp
from xtr_mime import Address, Message, RawMessage
from xtr_mime.header import Headers, ParameterizedHeader

from xtr_mailer import Envelope
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import MessengerTransportListener

_ENVELOPE = Envelope(Address("sender@example.com"), [Address("recipient@example.com")])


def _message(transports: str) -> Message:
    return Message(Headers().add_text_header("X-Bus-Transport", transports))


def test_no_messenger_transport_stamps_by_default() -> None:
    event = MessageEvent(Message(Headers()), _ENVELOPE, "smtp", queued=True)

    MessengerTransportListener().on_message(event)

    assert event.get_stamps() == []


def test_messenger_transport_stamp_via_header() -> None:
    message = _message("async")
    event = MessageEvent(message, _ENVELOPE, "smtp", queued=True)

    MessengerTransportListener().on_message(event)

    assert event.get_stamps() == [TransportNamesStamp(("async",))]
    assert not message.get_headers().has("X-Bus-Transport")


def test_messenger_transport_stamps_via_header() -> None:
    name = "söme_very_long_and_weïrd transport name-for-messenger!"
    message = _message(" async , async1," + name)
    event = MessageEvent(message, _ENVELOPE, "smtp", queued=True)

    MessengerTransportListener().on_message(event)

    assert event.get_stamps() == [TransportNamesStamp(("async", "async1", name))]
    assert not message.get_headers().has("X-Bus-Transport")


def test_an_email_sent_now_keeps_its_header() -> None:
    message = _message("async")
    event = MessageEvent(message, _ENVELOPE, "smtp")

    MessengerTransportListener().on_message(event)

    assert message.get_headers().has("X-Bus-Transport")


def test_a_header_that_is_not_text_names_the_transports_as_it_renders() -> None:
    message = Message(Headers(ParameterizedHeader("X-Bus-Transport", "async")))
    event = MessageEvent(message, _ENVELOPE, "smtp", queued=True)

    MessengerTransportListener().on_message(event)

    assert event.get_stamps() == [TransportNamesStamp(("async",))]


def test_queued_raw_bytes_get_no_stamp() -> None:
    event = MessageEvent(RawMessage("X-Bus-Transport: async\r\n\r\n"), _ENVELOPE, "smtp", True)

    MessengerTransportListener().on_message(event)

    assert event.get_stamps() == []


def test_it_runs_at_the_default_priority() -> None:
    assert MessengerTransportListener.PRIORITY == 0
