"""The listener keeping every email event, for tests to assert on."""

from __future__ import annotations

import pytest
from xtr_mime import Address, Email
from xtr_service_contracts import ResetInterface

from xtr_mailer import Envelope
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import MessageLoggerListener


def _event() -> MessageEvent:
    email = Email().from_("from@example.com").to("to@example.com").text("Hello!")
    envelope = Envelope(Address("from@example.com"), [Address("to@example.com")])
    return MessageEvent(email, envelope, "smtp")


def test_messages_are_logged_by_default() -> None:
    listener = MessageLoggerListener()

    listener.on_message(_event())

    assert len(listener.get_events().get_events()) == 1


def test_messages_are_discarded_while_disabled() -> None:
    listener = MessageLoggerListener(lambda: True)

    listener.on_message(_event())

    assert listener.get_events().get_events() == []


def test_the_disabled_state_is_checked_on_each_message() -> None:
    disabled = [True]
    listener = MessageLoggerListener(lambda: disabled[0])

    listener.on_message(_event())
    disabled[0] = False
    listener.on_message(_event())

    assert len(listener.get_events().get_events()) == 1


@pytest.mark.anyio
async def test_reset_drops_logged_messages() -> None:
    listener = MessageLoggerListener()
    listener.on_message(_event())

    await listener.reset()

    assert listener.get_events().get_events() == []


def test_it_is_reset_between_units_of_work() -> None:
    assert isinstance(MessageLoggerListener(), ResetInterface)


def test_it_runs_after_every_other_listener_of_the_event() -> None:
    assert MessageLoggerListener.PRIORITY == -255
