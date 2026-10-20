from __future__ import annotations

from xtr_notifier.event import MessageEvent, NotificationEvents
from xtr_notifier.message import ChatMessage, SmsMessage


def _events() -> tuple[NotificationEvents, MessageEvent, MessageEvent, MessageEvent]:
    events = NotificationEvents()
    slack = MessageEvent(ChatMessage("one", transport="slack"))
    unnamed = MessageEvent(SmsMessage("+3312345678", "two"))
    slack_again = MessageEvent(ChatMessage("three", transport="slack"), queued=True)
    for event in (slack, unnamed, slack_again):
        events.add(event)
    return events, slack, unnamed, slack_again


def test_it_starts_empty() -> None:
    events = NotificationEvents()

    assert events.get_events() == []
    assert events.get_messages() == []
    assert events.transports == []


def test_it_lists_every_event_in_order() -> None:
    events, slack, unnamed, slack_again = _events()

    assert events.get_events() == [slack, unnamed, slack_again]


def test_it_lists_each_transport_once_an_unnamed_one_as_empty() -> None:
    events, *_ = _events()

    assert events.transports == ["slack", ""]


def test_it_filters_events_by_transport() -> None:
    events, slack, unnamed, slack_again = _events()

    assert events.get_events("slack") == [slack, slack_again]
    assert events.get_events("") == [unnamed]
    assert events.get_events("telegram") == []


def test_it_lists_the_messages_of_the_events() -> None:
    events, slack, _, slack_again = _events()

    assert events.get_messages("slack") == [slack.message, slack_again.message]
    assert len(events.get_messages()) == 3
