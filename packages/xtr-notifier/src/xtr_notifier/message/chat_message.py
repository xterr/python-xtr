"""A message for a chat provider."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from xtr_notifier.notification.notification_summary import NotificationSummary

from .message_options import MessageOptions

if TYPE_CHECKING:
    from xtr_notifier.notification import Notification

__all__ = ["ChatMessage"]


@final
@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A message for a chat provider — a Slack channel, a Telegram chat.

    A frozen value, so it can be queued on a message bus and sent by another
    process; a change is a copy, made with a ``with_*`` method.

    Attributes:
        subject: The text to post.
        options: The provider's options, or ``None`` for its defaults.
        transport: The transport to send through, or ``None`` for the first that can.
        notification: What the message was made from, for a provider that
            renders more than the subject; ``None`` for a message built directly.
    """

    subject: str
    options: MessageOptions | None = None
    transport: str | None = None
    notification: NotificationSummary | None = None

    @classmethod
    def from_notification(cls, notification: Notification) -> ChatMessage:
        """Make the chat message ``notification`` says by default."""
        return cls(
            notification.subject, notification=NotificationSummary.from_notification(notification)
        )

    @property
    def recipient_id(self) -> str | None:
        """Who the message goes to, from the options; ``None`` for the transport's default."""
        return None if self.options is None else self.options.recipient_id

    def with_subject(self, subject: str) -> ChatMessage:
        """Return a copy posting ``subject`` instead."""
        return dataclasses.replace(self, subject=subject)

    def with_options(self, options: MessageOptions | None) -> ChatMessage:
        """Return a copy carrying ``options`` instead."""
        return dataclasses.replace(self, options=options)

    def with_transport(self, transport: str | None) -> ChatMessage:
        """Return a copy sent through the transport named ``transport``."""
        return dataclasses.replace(self, transport=transport)
