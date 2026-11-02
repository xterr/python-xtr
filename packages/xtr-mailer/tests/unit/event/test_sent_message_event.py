"""An email a transport sent."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event
from xtr_mime import Address, Email

from xtr_mailer import Envelope, SentMessage
from xtr_mailer.event import SentMessageEvent


def test_it_carries_what_the_transport_sent() -> None:
    email = Email().from_("from@example.com").to("to@example.com").text("Hello!")
    sent = SentMessage(email, Envelope(Address("from@example.com"), [Address("to@example.com")]))

    event = SentMessageEvent(sent)

    assert isinstance(event, Event)
    assert event.get_message() is sent
