from __future__ import annotations

import dataclasses

import pytest

from xtr_notifier.message import ChatMessage, MessageInterface, MessageOptions
from xtr_notifier.notification import Importance, Notification, NotificationSummary


def test_it_is_built_with_a_subject_alone() -> None:
    message = ChatMessage("Hello")

    assert isinstance(message, MessageInterface)
    assert message.subject == "Hello"
    assert message.options is None
    assert message.transport is None
    assert message.notification is None
    assert message.recipient_id is None


def test_its_recipient_comes_from_its_options() -> None:
    message = ChatMessage("Hello", MessageOptions("slack", "ops"))

    assert message.recipient_id == "ops"


def test_it_is_copied_with_another_subject_options_or_transport() -> None:
    message = ChatMessage("Hello")
    options = MessageOptions("slack", "ops")

    changed = message.with_subject("Bye").with_options(options).with_transport("slack")

    assert changed == ChatMessage("Bye", options, "slack")
    assert message == ChatMessage("Hello")


def test_it_is_frozen() -> None:
    message = ChatMessage("Hello")

    with pytest.raises(dataclasses.FrozenInstanceError):
        # Assigning a frozen field is the refusal under test, which both checkers report.
        message.subject = "Bye"  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[invalid-assignment]


def test_it_is_made_from_a_notification_keeping_a_summary_of_it() -> None:
    notification = Notification("Disk full", content="98%", importance=Importance.URGENT)

    message = ChatMessage.from_notification(notification)

    assert message.subject == "Disk full"
    assert message.notification == NotificationSummary.from_notification(notification)
