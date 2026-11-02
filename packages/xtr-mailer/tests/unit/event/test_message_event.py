"""An email about to be sent or queued, which listeners may change, reject or stamp."""

from __future__ import annotations

import pytest
from xtr_event_dispatcher_contracts import Event
from xtr_messenger.stamp import DelayStamp
from xtr_mime import Address, Email, RawMessage

from xtr_mailer import Envelope, LogicError
from xtr_mailer.event import MessageEvent


def _envelope() -> Envelope:
    return Envelope(Address("from@example.com"), [Address("to@example.com")])


def _email() -> Email:
    return Email().from_("from@example.com").to("to@example.com").text("Hello!")


def test_it_carries_the_message_envelope_and_transport_and_is_not_queued_by_default() -> None:
    message = _email()
    envelope = _envelope()

    event = MessageEvent(message, envelope, "smtp")

    assert isinstance(event, Event)
    assert event.get_message() is message
    assert event.get_envelope() is envelope
    assert event.get_transport() == "smtp"
    assert event.is_queued() is False


def test_it_says_when_the_message_is_queued() -> None:
    assert MessageEvent(_email(), _envelope(), "smtp", queued=True).is_queued() is True


def test_a_listener_replaces_the_message() -> None:
    event = MessageEvent(_email(), _envelope(), "smtp")
    replacement = RawMessage(b"Subject: replaced\r\n\r\nHello")

    event.set_message(replacement)

    assert event.get_message() is replacement


def test_a_listener_replaces_the_envelope() -> None:
    event = MessageEvent(_email(), _envelope(), "smtp")
    replacement = Envelope(Address("bounce@example.com"), [Address("other@example.com")])

    event.set_envelope(replacement)

    assert event.get_envelope() is replacement


def test_it_is_not_rejected_until_a_listener_rejects_it() -> None:
    event = MessageEvent(_email(), _envelope(), "smtp")

    assert event.is_rejected() is False
    assert event.is_propagation_stopped() is False


def test_rejecting_it_stops_the_listeners_after_this_one() -> None:
    event = MessageEvent(_email(), _envelope(), "smtp")

    event.reject()

    assert event.is_rejected() is True
    assert event.is_propagation_stopped() is True


def test_a_queued_message_has_no_stamps_until_a_listener_adds_one() -> None:
    assert MessageEvent(_email(), _envelope(), "smtp", queued=True).get_stamps() == []


def test_a_listener_stamps_a_queued_message_in_order() -> None:
    event = MessageEvent(_email(), _envelope(), "smtp", queued=True)
    first = DelayStamp(1000)
    second = DelayStamp(2000)

    event.add_stamp(first)
    event.add_stamp(second)

    assert event.get_stamps() == [first, second]


def test_changing_the_returned_stamps_leaves_the_event_alone() -> None:
    event = MessageEvent(_email(), _envelope(), "smtp", queued=True)

    event.get_stamps().append(DelayStamp(1000))

    assert event.get_stamps() == []


def test_a_message_sent_now_takes_no_stamp() -> None:
    event = MessageEvent(_email(), _envelope(), "smtp")

    with pytest.raises(LogicError) as caught:
        event.add_stamp(DelayStamp(1000))

    assert str(caught.value) == (
        'Cannot call "MessageEvent.add_stamp()" on a message that is not meant to be queued.'
    )


def test_a_message_sent_now_has_no_stamps_to_read() -> None:
    event = MessageEvent(_email(), _envelope(), "smtp")

    with pytest.raises(LogicError) as caught:
        _ = event.get_stamps()

    assert str(caught.value) == (
        'Cannot call "MessageEvent.get_stamps()" on a message that is not meant to be queued.'
    )
