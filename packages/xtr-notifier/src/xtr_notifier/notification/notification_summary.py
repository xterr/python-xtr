"""What a message keeps of the notification it was made from."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .importance import Importance

if TYPE_CHECKING:
    from .notification import Notification

__all__ = ["NotificationSummary"]


@dataclass(frozen=True, slots=True)
class NotificationSummary:
    """The parts of a notification a provider renders richer output from.

    A message made from a notification carries this copy, not the notification:
    a provider shows the emoji, colours by importance or attaches the traceback
    from it, and because every field is a plain string the message still
    crosses a message bus's wire — a notification, with its live exception and
    whatever an application subclass adds, would not.
    """

    subject: str
    content: str = ""
    importance: Importance = Importance.HIGH
    emoji: str = ""
    exception_as_string: str = ""

    @classmethod
    def from_notification(cls, notification: Notification) -> NotificationSummary:
        """Copy what a message renders from ``notification``."""
        return cls(
            subject=notification.subject,
            content=notification.content,
            importance=notification.importance,
            emoji=notification.emoji,
            exception_as_string=notification.exception_as_string,
        )
