"""A button of a custom reply keyboard."""

from __future__ import annotations

from typing import Self, final

from .abstract_keyboard_button import AbstractKeyboardButton

__all__ = ["KeyboardButton"]


@final
class KeyboardButton(AbstractKeyboardButton):
    """A reply button: tapped, it sends its text — or the user's contact, location or a poll."""

    def __init__(self, text: str) -> None:
        """Label the button ``text``, which is what a tap sends."""
        super().__init__()
        self._options["text"] = text

    def request_contact(self, request: bool) -> Self:
        """Send the user's phone contact when tapped."""
        self._options["request_contact"] = request
        return self

    def request_location(self, request: bool) -> Self:
        """Send the user's location when tapped."""
        self._options["request_location"] = request
        return self

    def request_poll_type(self, poll_type: str) -> Self:
        """Ask the user to create a poll of ``poll_type`` (``quiz`` or ``regular``) when tapped."""
        self._options["request_poll"] = {"type": poll_type}
        return self
