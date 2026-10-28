"""A custom keyboard shown in place of the user's own."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from .abstract_telegram_reply_markup import AbstractTelegramReplyMarkup

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .button.keyboard_button import KeyboardButton

__all__ = ["ReplyKeyboardMarkup"]


@final
class ReplyKeyboardMarkup(AbstractTelegramReplyMarkup):
    """Rows of reply buttons replacing the user's keyboard; a tap sends the button's text."""

    def __init__(self) -> None:
        """Start with no row."""
        super().__init__()
        self._rows: list[list[dict[str, object]]] = []
        self._options["keyboard"] = self._rows

    def keyboard(self, buttons: Iterable[KeyboardButton]) -> Self:
        """Add a row of ``buttons`` below the rows added so far."""
        self._rows.append([button.to_array() for button in buttons])
        return self

    def resize_keyboard(self, resize: bool) -> Self:
        """Fit the keyboard's height to its buttons rather than the standard keyboard's."""
        self._options["resize_keyboard"] = resize
        return self

    def one_time_keyboard(self, one_time: bool) -> Self:
        """Hide the keyboard once a button is used."""
        self._options["one_time_keyboard"] = one_time
        return self

    def selective(self, selective: bool) -> Self:
        """Show it only to the users the message mentions and the sender replied to."""
        self._options["selective"] = selective
        return self
