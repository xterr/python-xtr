"""The base of every reply markup a message can carry."""

from __future__ import annotations

import copy
from abc import ABC

__all__ = ["AbstractTelegramReplyMarkup"]


class AbstractTelegramReplyMarkup(ABC):  # noqa: B024 -- abstract by role: only its subclasses mean anything to the bot API
    """What the chat shows under a message: a keyboard, its removal, or a forced reply.

    A subclass fills :attr:`_options` with the bot API's fields;
    :meth:`~xtr_telegram_notifier.TelegramOptions.reply_markup` renders it into
    the message's options.
    """

    def __init__(self) -> None:
        """Start with no field set."""
        self._options: dict[str, object] = {}

    def to_array(self) -> dict[str, object]:
        """Render the markup as the bot API reads it — a copy, so it stays as it was."""
        return copy.deepcopy(self._options)
