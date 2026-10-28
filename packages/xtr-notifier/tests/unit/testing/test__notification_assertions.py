from __future__ import annotations

import pytest

from xtr_notifier.event import MessageEvent, NotificationEvents
from xtr_notifier.message import ChatMessage, SmsMessage
from xtr_notifier.testing import (
    assert_notification_count,
    assert_notification_is_not_queued,
    assert_notification_is_queued,
    assert_notification_subject_contains,
    assert_notification_subject_not_contains,
    assert_notification_transport_is,
    assert_notification_transport_is_not,
    assert_queued_notification_count,
)


def _events() -> NotificationEvents:
    events = NotificationEvents()
    events.add(MessageEvent(ChatMessage("one", transport="slack")))
    events.add(MessageEvent(ChatMessage("two", transport="slack"), queued=True))
    events.add(MessageEvent(SmsMessage("+33", "three")))
    return events


def test_it_counts_the_notifications_sent() -> None:
    assert_notification_count(_events(), 2)
    assert_notification_count(_events(), 1, "slack")


def test_it_fails_on_a_wrong_count_of_notifications_sent() -> None:
    with pytest.raises(AssertionError) as caught:
        assert_notification_count(_events(), 3, "slack")

    assert str(caught.value) == 'Expected 3 notification(s) sent on "slack", found 1.'


def test_it_counts_the_notifications_queued() -> None:
    assert_queued_notification_count(_events(), 1)
    assert_queued_notification_count(_events(), 0, "")


def test_it_fails_on_a_wrong_count_of_notifications_queued() -> None:
    with pytest.raises(AssertionError) as caught:
        assert_queued_notification_count(_events(), 2)

    assert str(caught.value) == "Expected 2 notification(s) queued, found 1."


def test_it_tells_a_queued_notification_from_one_sent() -> None:
    queued = MessageEvent(ChatMessage("x"), queued=True)
    sent = MessageEvent(ChatMessage("x"))

    assert_notification_is_queued(queued)
    assert_notification_is_not_queued(sent)
    with pytest.raises(AssertionError, match=r"^The notification is not queued\.$"):
        assert_notification_is_queued(sent)
    with pytest.raises(AssertionError, match=r"^The notification is queued\.$"):
        assert_notification_is_not_queued(queued)


def test_it_checks_the_subject_holds_a_text() -> None:
    message = ChatMessage("Disk almost full")

    assert_notification_subject_contains(message, "almost")
    assert_notification_subject_not_contains(message, "empty")
    with pytest.raises(AssertionError) as caught:
        assert_notification_subject_contains(message, "empty")
    assert (
        str(caught.value) == 'The notification subject "Disk almost full" does not contain "empty".'
    )
    with pytest.raises(AssertionError, match=r'^The notification subject .* contains "almost"\.$'):
        assert_notification_subject_not_contains(message, "almost")


def test_it_checks_the_transport_a_notification_names() -> None:
    message = ChatMessage("x", transport="slack")

    assert_notification_transport_is(message, "slack")
    assert_notification_transport_is(ChatMessage("x"), None)
    assert_notification_transport_is_not(message, "telegram")
    with pytest.raises(AssertionError) as caught:
        assert_notification_transport_is(message, "telegram")
    assert str(caught.value) == "The notification transport is 'slack', not 'telegram'."
    with pytest.raises(AssertionError, match=r"^The notification transport is 'slack'\.$"):
        assert_notification_transport_is_not(message, "slack")
