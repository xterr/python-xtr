"""A mail provider's report on what the recipient did with a message."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, final

from xtr_serializer import discriminator_name

from xtr_remote_event.event.mailer.abstract_mailer_event import AbstractMailerEvent

__all__ = ["MailerEngagementEvent"]


@discriminator_name("mailer_engagement")
@final
@dataclass(frozen=True, slots=True, kw_only=True)
class MailerEngagementEvent(AbstractMailerEvent):
    """What the recipient did with a message, as far as its provider could tell.

    ``name`` is one of the constants below, whatever word the provider used, so
    a consumer matches on the constants and works with every provider.

    Written under ``"mailer_engagement"`` wherever a field declares
    :class:`~xtr_remote_event.RemoteEvent`, and read back as this type.

    A provider only sees what its tracking shows — an open through an image it
    serves, a click through a link it rewrote — so read these as signals rather
    than proof: a mail client that blocks images opens unseen, and a scanner
    that follows links clicks unasked.
    """

    OPEN: ClassVar[str] = "open"
    """The recipient opened the message."""

    CLICK: ClassVar[str] = "click"
    """The recipient followed a link in the message."""

    SPAM: ClassVar[str] = "spam"
    """The recipient marked the message as spam."""

    UNSUBSCRIBE: ClassVar[str] = "unsubscribe"
    """The recipient asked for no more mail."""
