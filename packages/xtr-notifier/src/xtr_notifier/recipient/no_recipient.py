"""The recipient of a notification sent to nobody in particular."""

from __future__ import annotations

from typing import final

from .recipient_interface import RecipientInterface

__all__ = ["NoRecipient"]


@final
class NoRecipient(RecipientInterface):
    """Nobody in particular: a notification to a chat room or a push topic goes here.

    It has neither an email nor a phone, so a channel that needs one refuses it
    instead of sending to an empty address.
    """

    __slots__ = ()
