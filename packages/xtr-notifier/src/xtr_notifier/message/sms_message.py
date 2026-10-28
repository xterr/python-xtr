"""A text message to a phone number."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from xtr_notifier.exception import InvalidArgumentError
from xtr_notifier.notification.notification_summary import NotificationSummary

from .message_options import MessageOptions

if TYPE_CHECKING:
    from xtr_notifier.notification import Notification
    from xtr_notifier.recipient import SmsRecipientInterface

__all__ = ["SmsMessage"]


@final
@dataclass(frozen=True, slots=True)
class SmsMessage:
    """A text message to a phone number.

    A frozen value, so it can be queued on a message bus and sent by another
    process; a change is a copy, made with a ``with_*`` method. The phone number
    is checked whenever one is made, copies included.

    Attributes:
        phone: The number to send to, international form with no spaces.
        subject: The text to send.
        from_: The sender to show, or ``""`` for the transport's own.
        options: The provider's options, or ``None`` for its defaults.
        transport: The transport to send through, or ``None`` for the first that can.
        notification: What the message was made from, or ``None``.
    """

    phone: str
    subject: str
    from_: str = ""
    options: MessageOptions | None = None
    transport: str | None = None
    notification: NotificationSummary | None = None

    def __post_init__(self) -> None:
        """Refuse a message with nowhere to go.

        Raises:
            InvalidArgumentError: If the phone number is empty.
        """
        if not self.phone:
            raise InvalidArgumentError(
                f'"{type(self).__name__}" needs a phone number, it cannot be empty.'
            )

    @classmethod
    def from_notification(
        cls, notification: Notification, recipient: SmsRecipientInterface
    ) -> SmsMessage:
        """Make the text message ``notification`` says by default, to ``recipient``."""
        return cls(
            recipient.phone,
            notification.subject,
            notification=NotificationSummary.from_notification(notification),
        )

    @property
    def recipient_id(self) -> str:
        """The phone number: a text message always names who it goes to."""
        return self.phone

    def with_phone(self, phone: str) -> SmsMessage:
        """Return a copy sent to ``phone`` instead.

        Raises:
            InvalidArgumentError: If ``phone`` is empty.
        """
        return dataclasses.replace(self, phone=phone)

    def with_subject(self, subject: str) -> SmsMessage:
        """Return a copy sending ``subject`` instead."""
        return dataclasses.replace(self, subject=subject)

    def with_from(self, from_: str) -> SmsMessage:
        """Return a copy showing ``from_`` as its sender."""
        return dataclasses.replace(self, from_=from_)

    def with_options(self, options: MessageOptions | None) -> SmsMessage:
        """Return a copy carrying ``options`` instead."""
        return dataclasses.replace(self, options=options)

    def with_transport(self, transport: str | None) -> SmsMessage:
        """Return a copy sent through the transport named ``transport``."""
        return dataclasses.replace(self, transport=transport)
