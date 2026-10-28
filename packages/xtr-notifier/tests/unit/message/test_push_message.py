from __future__ import annotations

from xtr_notifier.message import MessageInterface, MessageOptions, PushMessage
from xtr_notifier.notification import Notification, NotificationSummary


def test_it_is_built_with_a_subject_and_a_content() -> None:
    message = PushMessage("Hello", "World")

    assert isinstance(message, MessageInterface)
    assert message.subject == "Hello"
    assert message.content == "World"
    assert message.recipient_id is None


def test_it_is_copied_with_another_subject() -> None:
    assert PushMessage("Hello", "World").with_subject("dlrow olleH").subject == "dlrow olleH"


def test_it_is_copied_with_another_content() -> None:
    assert PushMessage("Hello", "World").with_content("dlrow olleH").content == "dlrow olleH"


def test_it_is_copied_with_another_transport() -> None:
    assert PushMessage("Hello", "World").with_transport("next_one").transport == "next_one"


def test_it_is_copied_with_options_naming_its_recipient() -> None:
    message = PushMessage("Hello", "World").with_options(MessageOptions("ntfy", "topic"))

    assert message.recipient_id == "topic"


def test_it_is_made_from_a_notification() -> None:
    notification = Notification("Hello", content="World")

    message = PushMessage.from_notification(notification)

    assert message.subject == "Hello"
    assert message.content == "World"
    assert message.notification == NotificationSummary.from_notification(notification)
