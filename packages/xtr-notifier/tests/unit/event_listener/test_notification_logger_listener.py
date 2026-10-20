from __future__ import annotations

import pytest
from xtr_service_contracts import ResetInterface

from xtr_notifier.event import MessageEvent
from xtr_notifier.event_listener import NotificationLoggerListener
from xtr_notifier.message import SmsMessage


def _event() -> MessageEvent:
    return MessageEvent(SmsMessage("+37255555555", "Hello!"))


def test_notifications_are_logged_by_default() -> None:
    listener = NotificationLoggerListener()

    listener.on_notification(_event())

    assert len(listener.events.get_events()) == 1


def test_notifications_are_discarded_while_disabled() -> None:
    listener = NotificationLoggerListener(lambda: True)

    listener.on_notification(_event())

    assert listener.events.get_events() == []


def test_the_disabled_state_is_checked_on_each_notification() -> None:
    disabled = [True]
    listener = NotificationLoggerListener(lambda: disabled[0])

    listener.on_notification(_event())
    disabled[0] = False
    listener.on_notification(_event())

    assert len(listener.events.get_events()) == 1


@pytest.mark.anyio
async def test_reset_drops_logged_notifications() -> None:
    listener = NotificationLoggerListener()
    listener.on_notification(_event())

    await listener.reset()

    assert listener.events.get_events() == []


def test_it_is_reset_between_units_of_work_and_runs_after_other_listeners() -> None:
    assert isinstance(NotificationLoggerListener(), ResetInterface)
    assert NotificationLoggerListener.PRIORITY == -255
