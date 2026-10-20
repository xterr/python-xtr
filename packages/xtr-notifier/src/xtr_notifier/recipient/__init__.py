"""Who a notification is sent to, and what each can be reached by."""

from __future__ import annotations

from .email_recipient_interface import EmailRecipientInterface
from .no_recipient import NoRecipient
from .recipient import Recipient
from .recipient_interface import RecipientInterface
from .sms_recipient_interface import SmsRecipientInterface

__all__ = [
    "EmailRecipientInterface",
    "NoRecipient",
    "Recipient",
    "RecipientInterface",
    "SmsRecipientInterface",
]
