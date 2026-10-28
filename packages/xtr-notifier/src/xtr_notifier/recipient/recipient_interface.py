"""Who a notification is for."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["RecipientInterface"]


@runtime_checkable
class RecipientInterface(Protocol):
    """Whoever a notification is sent to.

    It asks for nothing: what a recipient can be reached by is said by the
    narrower interfaces — an email, a phone number — and a channel checks for
    the one it needs. A notification sent to nobody in particular, to a chat
    room say, goes to a :class:`~xtr_notifier.recipient.no_recipient.NoRecipient`.
    """
