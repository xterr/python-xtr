from __future__ import annotations

import pytest
from typing_extensions import override
from xtr_logging_contracts import Level
from xtr_logging_contracts.exception import InvalidLevelError

from xtr_notifier.notification import Importance, Notification
from xtr_notifier.recipient import NoRecipient, Recipient, RecipientInterface


class _DiskFullError(Exception):
    pass


def _fail() -> None:
    raise _DiskFullError("disk almost full")


def _raise_and_catch() -> _DiskFullError:
    try:
        _fail()
    except _DiskFullError as error:
        return error
    raise AssertionError


def test_it_defaults_to_high_importance_and_empty_texts() -> None:
    notification = Notification()

    assert notification.subject == ""
    assert notification.content == ""
    assert notification.importance is Importance.HIGH
    assert notification.emoji == ""
    assert notification.exception is None
    assert notification.exception_as_string == ""
    assert notification.channels == ()


def test_it_keeps_what_it_is_built_with() -> None:
    notification = Notification(
        "Order shipped",
        content="Your order is on its way.",
        importance=Importance.LOW,
        emoji="📦",
        channels=["chat/slack", "sms"],
    )

    assert notification.subject == "Order shipped"
    assert notification.content == "Your order is on its way."
    assert notification.importance is Importance.LOW
    assert notification.emoji == "📦"
    assert notification.channels == ("chat/slack", "sms")


def test_its_channels_are_the_same_for_every_recipient_unless_overridden() -> None:
    notification = Notification("subject", channels=["chat"])

    assert notification.get_channels(NoRecipient()) == ("chat",)
    assert notification.get_channels(Recipient("a@example.test")) == ("chat",)


def test_a_subclass_picks_channels_per_recipient() -> None:
    class _PerRecipient(Notification):
        @override
        def get_channels(self, recipient: RecipientInterface) -> tuple[str, ...]:
            return ("sms",) if isinstance(recipient, Recipient) else ("chat",)

    notification = _PerRecipient("subject")

    assert notification.get_channels(Recipient(phone="+0815")) == ("sms",)
    assert notification.get_channels(NoRecipient()) == ("chat",)


def test_it_is_built_from_an_exception() -> None:
    error = _raise_and_catch()

    notification = Notification.from_exception(error, channels=["chat"])

    assert notification.subject == "_DiskFullError: disk almost full"
    assert notification.exception is error
    assert notification.channels == ("chat",)
    assert notification.exception_as_string.startswith("Traceback (most recent call last):")
    assert notification.exception_as_string.endswith("_DiskFullError: disk almost full")
    assert "_fail" in notification.exception_as_string


def test_an_exception_given_at_build_names_an_empty_subject() -> None:
    notification = Notification(exception=_raise_and_catch())

    assert notification.subject == "_DiskFullError: disk almost full"


def test_a_subject_given_with_an_exception_is_kept() -> None:
    notification = Notification("Backup failed", exception=_raise_and_catch())

    assert notification.subject == "Backup failed"
    assert notification.exception_as_string.endswith("_DiskFullError: disk almost full")


@pytest.mark.parametrize(
    ("importance", "emoji"),
    [
        (Importance.URGENT, "🌩️"),
        (Importance.HIGH, "🌧️"),
        (Importance.MEDIUM, "🌦️"),
        (Importance.LOW, "⛅"),
    ],
)
def test_its_default_emoji_follows_the_importance_when_an_exception_is_attached(
    importance: Importance, emoji: str
) -> None:
    notification = Notification(exception=_raise_and_catch(), importance=importance)

    assert notification.emoji == emoji


def test_an_emoji_given_wins_over_the_default() -> None:
    notification = Notification(exception=_raise_and_catch(), emoji="🔥")

    assert notification.emoji == "🔥"


@pytest.mark.parametrize(
    ("level", "importance"),
    [
        ("emergency", Importance.URGENT),
        ("alert", Importance.URGENT),
        ("critical", Importance.URGENT),
        ("ERROR", Importance.HIGH),
        (Level.ERROR, Importance.HIGH),
        ("warning", Importance.LOW),
        ("notice", Importance.LOW),
        ("info", Importance.LOW),
        ("debug", Importance.LOW),
    ],
)
def test_it_reads_an_importance_from_a_log_level(
    level: str | Level, importance: Importance
) -> None:
    assert Notification.importance_from_level(level) is importance


def test_it_refuses_a_log_level_that_does_not_exist() -> None:
    with pytest.raises(InvalidLevelError):
        _ = Notification.importance_from_level("loud")
