from __future__ import annotations

import dataclasses

import pytest

from xtr_notifier.notification import Importance, Notification, NotificationSummary


def test_it_copies_what_a_message_renders_from_a_notification() -> None:
    notification = Notification(
        content="body", importance=Importance.URGENT, exception=RuntimeError("boom")
    )

    summary = NotificationSummary.from_notification(notification)

    assert summary == NotificationSummary(
        subject="RuntimeError: boom",
        content="body",
        importance=Importance.URGENT,
        emoji="🌩️",
        exception_as_string=notification.exception_as_string,
    )


def test_it_is_frozen() -> None:
    summary = NotificationSummary("subject")

    with pytest.raises(dataclasses.FrozenInstanceError):
        # Assigning a frozen field is the refusal under test, which both checkers report.
        summary.subject = "changed"  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[invalid-assignment]


def test_it_defaults_to_high_importance_and_empty_texts() -> None:
    assert NotificationSummary("subject") == NotificationSummary(
        subject="subject",
        content="",
        importance=Importance.HIGH,
        emoji="",
        exception_as_string="",
    )
