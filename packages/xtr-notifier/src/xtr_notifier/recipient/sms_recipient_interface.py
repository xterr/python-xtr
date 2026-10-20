"""A recipient reached by text message."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .recipient_interface import RecipientInterface

__all__ = ["SmsRecipientInterface"]


@runtime_checkable
class SmsRecipientInterface(RecipientInterface, Protocol):
    """A recipient with a phone number, which the SMS channel needs."""

    @property
    def phone(self) -> str:
        """The phone number, international form with no spaces (``+3312345678``)."""
        ...
