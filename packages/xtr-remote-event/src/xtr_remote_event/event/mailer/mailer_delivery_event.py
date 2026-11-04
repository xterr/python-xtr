"""A mail provider's report on getting a message to its recipient."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, final

from xtr_serializer import discriminator_name

from xtr_remote_event.event.mailer.abstract_mailer_event import AbstractMailerEvent

__all__ = ["MailerDeliveryEvent"]


@discriminator_name("mailer_delivery")
@final
@dataclass(frozen=True, slots=True, kw_only=True)
class MailerDeliveryEvent(AbstractMailerEvent):
    """Where a message stands on its way to its recipient, as its provider reports it.

    ``name`` is one of the constants below, whatever word the provider used, so
    a consumer matches on the constants and works with every provider.

    Written under ``"mailer_delivery"`` wherever a field declares
    :class:`~xtr_remote_event.RemoteEvent`, and read back as this type.

    Attributes:
        reason: Why it happened, in the provider's words — the receiving
            server's answer to a bounce, for one — or ``""`` when it gave none.
    """

    RECEIVED: ClassVar[str] = "received"
    """The provider accepted the message to send."""

    DROPPED: ClassVar[str] = "dropped"
    """The provider refused the message, or will not try to deliver it."""

    DELIVERED: ClassVar[str] = "delivered"
    """The recipient's server accepted the message."""

    DEFERRED: ClassVar[str] = "deferred"
    """Delivery failed for now; the provider will try again."""

    BOUNCE: ClassVar[str] = "bounce"
    """The recipient's server refused the message for good."""

    reason: str = ""
