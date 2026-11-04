"""An email a transport failed to send."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event
from xtr_mime import Email

from xtr_mailer import TransportError
from xtr_mailer.event import FailedMessageEvent


def test_it_carries_the_message_and_why_it_was_not_sent() -> None:
    email = Email().from_("from@example.com").to("to@example.com").text("Hello!")
    error = TransportError("Connection refused.")

    event = FailedMessageEvent(email, error)

    assert isinstance(event, Event)
    assert event.get_message() is email
    assert event.get_error() is error
