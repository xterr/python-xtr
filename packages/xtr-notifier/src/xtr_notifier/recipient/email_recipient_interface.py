"""A recipient reached by email."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .recipient_interface import RecipientInterface

__all__ = ["EmailRecipientInterface"]


@runtime_checkable
class EmailRecipientInterface(RecipientInterface, Protocol):
    """A recipient with an email address.

    No channel here sends email yet; the interface is part of the recipient
    model so the administrators a notifier is configured with keep their
    address for the channel that will.
    """

    @property
    def email(self) -> str:
        """The address to write to."""
        ...
