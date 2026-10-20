"""A push notification."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from xtr_notifier.notification.notification_summary import NotificationSummary

from .message_options import MessageOptions

if TYPE_CHECKING:
    from xtr_notifier.notification import Notification

__all__ = ["PushMessage"]


@final
@dataclass(frozen=True, slots=True)
class PushMessage:
    """A push notification: a title and a body, to a device, a topic or a subscriber.

    A frozen value, so it can be queued on a message bus and sent by another
    process; a change is a copy, made with a ``with_*`` method.

    Attributes:
        subject: The title.
        content: The body.
        options: The provider's options, or ``None`` for its defaults.
        transport: The transport to send through, or ``None`` for the first that can.
        notification: What the message was made from, or ``None``.
    """

    subject: str
    content: str
    options: MessageOptions | None = None
    transport: str | None = None
    notification: NotificationSummary | None = None

    @classmethod
    def from_notification(cls, notification: Notification) -> PushMessage:
        """Make the push notification ``notification`` says by default."""
        return cls(
            notification.subject,
            notification.content,
            notification=NotificationSummary.from_notification(notification),
        )

    @property
    def recipient_id(self) -> str | None:
        """Who the message goes to, from the options; ``None`` for the transport's default."""
        return None if self.options is None else self.options.recipient_id

    def with_subject(self, subject: str) -> PushMessage:
        """Return a copy titled ``subject`` instead."""
        return dataclasses.replace(self, subject=subject)

    def with_content(self, content: str) -> PushMessage:
        """Return a copy saying ``content`` instead."""
        return dataclasses.replace(self, content=content)

    def with_options(self, options: MessageOptions | None) -> PushMessage:
        """Return a copy carrying ``options`` instead."""
        return dataclasses.replace(self, options=options)

    def with_transport(self, transport: str | None) -> PushMessage:
        """Return a copy sent through the transport named ``transport``."""
        return dataclasses.replace(self, transport=transport)
