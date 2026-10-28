"""Taking a custom keyboard away."""

from __future__ import annotations

from typing import final

from .abstract_telegram_reply_markup import AbstractTelegramReplyMarkup

__all__ = ["ReplyKeyboardRemove"]


@final
class ReplyKeyboardRemove(AbstractTelegramReplyMarkup):
    """Removes the custom keyboard an earlier message showed."""

    def __init__(self, remove_keyboard: bool = False, selective: bool = False) -> None:
        """Remove the keyboard, for everyone or only the users the message mentions.

        Args:
            remove_keyboard: Whether the keyboard is removed.
            selective: Whether only the mentioned users, and the sender of the
                message replied to, lose it.
        """
        super().__init__()
        self._options["remove_keyboard"] = remove_keyboard
        self._options["selective"] = selective
