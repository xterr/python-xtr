"""Buttons shown right under a message."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from .abstract_telegram_reply_markup import AbstractTelegramReplyMarkup

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .button.inline_keyboard_button import InlineKeyboardButton

__all__ = ["InlineKeyboardMarkup"]


@final
class InlineKeyboardMarkup(AbstractTelegramReplyMarkup):
    """Rows of buttons attached to the message itself: links, callbacks, payments."""

    def __init__(self) -> None:
        """Start with no row."""
        super().__init__()
        self._rows: list[list[dict[str, object]]] = []
        self._options["inline_keyboard"] = self._rows

    def inline_keyboard(self, buttons: Iterable[InlineKeyboardButton]) -> Self:
        """Add a row of ``buttons`` below the rows added so far."""
        self._rows.append([button.to_array() for button in buttons])
        return self
