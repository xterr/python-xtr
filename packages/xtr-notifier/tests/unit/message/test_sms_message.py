from __future__ import annotations

import pytest

from xtr_notifier.exception import InvalidArgumentError
from xtr_notifier.message import MessageInterface, MessageOptions, SmsMessage
from xtr_notifier.notification import Notification, NotificationSummary
from xtr_notifier.recipient import Recipient


def test_it_is_built_with_a_phone_and_a_subject() -> None:
    message = SmsMessage("+3312345678", "subject")

    assert isinstance(message, MessageInterface)
    assert message.subject == "subject"
    assert message.phone == "+3312345678"
    assert message.from_ == ""


def test_it_is_built_with_a_sender() -> None:
    message = SmsMessage("+3312345678", "subject", "foo")

    assert message.subject == "subject"
    assert message.phone == "+3312345678"
    assert message.from_ == "foo"


def test_its_recipient_is_its_phone() -> None:
    message = SmsMessage("+3312345678", "subject", options=MessageOptions("twilio", "other"))

    assert message.recipient_id == "+3312345678"


def test_it_refuses_an_empty_phone() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SmsMessage("", "subject")

    assert str(caught.value) == '"SmsMessage" needs a phone number, it cannot be empty.'


def test_it_is_copied_with_another_phone() -> None:
    message = SmsMessage("+3312345678", "subject")

    assert message.with_phone("+4912345678").phone == "+4912345678"
    assert message.phone == "+3312345678"


def test_it_refuses_to_be_copied_with_an_empty_phone() -> None:
    message = SmsMessage("+3312345678", "subject")

    with pytest.raises(InvalidArgumentError) as caught:
        _ = message.with_phone("")

    assert str(caught.value) == '"SmsMessage" needs a phone number, it cannot be empty.'


def test_it_is_copied_with_another_sender_subject_options_or_transport() -> None:
    message = SmsMessage("+3312345678", "subject")
    options = MessageOptions("twilio")

    changed = (
        message.with_from("foo")
        .with_subject("other")
        .with_options(options)
        .with_transport("twilio")
    )

    assert changed == SmsMessage("+3312345678", "other", "foo", options, "twilio")


def test_it_is_made_from_a_notification_for_a_recipient() -> None:
    notification = Notification("Hello")

    message = SmsMessage.from_notification(notification, Recipient(phone="+3312345678"))

    assert message.phone == "+3312345678"
    assert message.subject == "Hello"
    assert message.notification == NotificationSummary.from_notification(notification)
